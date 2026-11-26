from fastapi.testclient import TestClient

from app.main import app

from .conftest import find_category


def upload(client, data: bytes, **form):
    return client.post("/api/imports/ing-csv", files={"file": ("umsaetze.csv", data, "text/csv")}, data=form)


def test_setup_only_once(admin):
    assert admin.get("/api/auth/setup").json() == {"needs_setup": False}
    r = admin.post("/api/auth/setup", json={"username": "zwei", "display_name": "Zwei", "password": "geheim123"})
    assert r.status_code == 409


def test_login_logout(admin):
    fresh = TestClient(app)
    assert fresh.get("/api/auth/me").status_code == 401
    assert fresh.post("/api/auth/login", json={"username": "alex", "password": "falsch"}).status_code == 401
    r = fresh.post("/api/auth/login", json={"username": "ALEX", "password": "geheim123"})
    assert r.status_code == 200
    assert fresh.get("/api/auth/me").json()["household_name"] == "Familie Test"
    assert fresh.post("/api/auth/logout").status_code == 204
    assert fresh.get("/api/auth/me").status_code == 401


def test_seeded_categories(admin):
    cats = admin.get("/api/categories").json()
    assert len(cats) == 14
    wohnen = cats[0]
    assert wohnen["name"] == "Wohnen" and len(wohnen["children"]) == 7
    assert next(c for c in cats if c["name"] == "Umbuchungen")["kind"] == "transfer"


def test_import_creates_account_and_skips_duplicates(admin, sample_csv):
    r = upload(admin, sample_csv)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["account_created"] is True
    assert body["rows_imported"] == 7 and body["rows_duplicate"] == 0

    again = upload(admin, sample_csv).json()
    assert again["account_created"] is False
    assert again["rows_imported"] == 0 and again["rows_duplicate"] == 7

    accounts = admin.get("/api/accounts").json()
    assert len(accounts) == 1
    assert accounts[0]["balance"] == "2345.67"
    assert accounts[0]["transaction_count"] == 7


def test_import_into_wrong_account_is_rejected(admin, sample_csv):
    acc = admin.post("/api/accounts", json={"name": "Extra", "iban": "DE02120300000000202051"}).json()
    r = upload(admin, sample_csv, account_id=str(acc["id"]))
    assert r.status_code == 400


def test_rules_categorize_on_import(admin, sample_csv, no_ai):
    supermarkt = find_category(admin, "Lebensmittel", "Supermarkt")
    r = admin.post("/api/rules", json={"category_id": supermarkt, "pattern": "rewe"})
    assert r.status_code == 201
    imp = upload(admin, sample_csv).json()
    assert imp["rows_categorized"] == 1
    rewe = admin.get("/api/transactions", params={"q": "REWE"}).json()["items"][0]
    assert rewe["category_id"] == supermarkt and rewe["category_source"] == "rule"


def test_manual_correction_with_rule(admin, sample_csv):
    upload(admin, sample_csv)
    baecker = find_category(admin, "Lebensmittel", "Bäcker/Metzger")
    items = admin.get("/api/transactions", params={"q": "Bäckerei"}).json()["items"]
    assert len(items) == 2
    r = admin.patch(f"/api/transactions/{items[0]['id']}", json={"category_id": baecker, "create_rule": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["transaction"]["category_source"] == "manual"
    assert body["rule"]["pattern"] == "Bäckerei Schmidt"
    assert body["other_changed"] == 1

    # A rule does not overwrite a manual assignment
    strom = find_category(admin, "Wohnen", "Strom")
    admin.post("/api/rules", json={"category_id": strom, "pattern": "Bäckerei", "priority": 10})
    admin.post("/api/rules/apply", json={"overwrite_rule_results": True})
    items = {t["id"]: t for t in admin.get("/api/transactions", params={"q": "Bäckerei"}).json()["items"]}
    assert items[body["transaction"]["id"]]["category_id"] == baecker
    other = next(t for i, t in items.items() if i != body["transaction"]["id"])
    assert other["category_id"] == strom


def test_transaction_detail(admin, sample_csv, no_ai):
    supermarkt = find_category(admin, "Lebensmittel", "Supermarkt")
    rule = admin.post("/api/rules", json={"category_id": supermarkt, "pattern": "rewe"}).json()
    upload(admin, sample_csv)
    rewe = admin.get("/api/transactions", params={"q": "REWE"}).json()["items"][0]
    r = admin.get(f"/api/transactions/{rewe['id']}")
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["purpose"] == "REWE SAGT DANKE 12345"
    assert detail["balance_after"] == "2345.67"
    assert detail["account"]["name"] == "Girokonto"
    assert detail["import_batch"]["source"] == "ing_csv"
    assert detail["import_batch"]["filename"] == "umsaetze.csv"
    assert detail["category_source"] == "rule"
    assert detail["rule"]["id"] == rule["id"] and detail["rule"]["match_count"] == 1
    # The CSV export carries no SEPA details
    assert detail["counterparty_iban"] is None and detail["mandate_id"] is None

    assert admin.get("/api/transactions/999999").status_code == 404


def test_transaction_detail_hidden_from_other_user(admin, sample_csv):
    upload(admin, sample_csv)
    acc = admin.get("/api/accounts").json()[0]
    admin.patch(f"/api/accounts/{acc['id']}", json={"shared": False})
    tx = admin.get("/api/transactions").json()["items"][0]
    admin.post("/api/users", json={"username": "kim", "display_name": "Kim", "password": "geheim123"})
    other = TestClient(app)
    other.post("/api/auth/login", json={"username": "kim", "password": "geheim123"})
    assert other.get(f"/api/transactions/{tx['id']}").status_code == 404


def test_overview(admin, sample_csv, no_ai):
    upload(admin, sample_csv)
    sparen = find_category(admin, "Umbuchungen", "Transfers zwischen eigenen Konten")
    miete = find_category(admin, "Wohnen", "Miete/Kredit")
    gehalt = find_category(admin, "Einnahmen", "Gehalt")
    admin.post("/api/rules", json={"category_id": sparen, "pattern": "Sparen", "field": "purpose"})
    admin.post("/api/rules", json={"category_id": miete, "pattern": "Vermieter"})
    admin.post("/api/rules", json={"category_id": gehalt, "pattern": "Arbeitgeber", "match_type": "starts_with"})

    nov = admin.get("/api/overview", params={"month": "2026-11"}).json()
    assert nov["expenses"] == "1098.32"
    # Salary from Oct 30 counts towards the November budget month
    assert nov["income"] == "3200.00"
    assert nov["income_from_previous_month"] == "3200.00"
    assert nov["uncategorized_count"] == 4
    wohnen = next(c for c in nov["expense_categories"] if c["name"] == "Wohnen")
    assert wohnen["amount"] == "950.00"
    assert wohnen["children"][0]["name"] == "Miete/Kredit"

    okt = admin.get("/api/overview", params={"month": "2026-10"}).json()
    assert okt["income"] == "0.00"
    assert okt["expenses"] == "0.00"  # Transfer does not count
    assert okt["transfers"] == "-500.00"
    hist = {h["month"]: h for h in nov["history"]}
    assert hist["2026-10"]["income"] == "0.00"
    assert hist["2026-11"]["income"] == "3200.00"
    assert hist["2026-10"]["expenses"] == "0.00"
    assert hist["2026-11"]["expenses"] == "1098.32"


def test_private_account_hidden_from_other_user(admin, sample_csv):
    upload(admin, sample_csv)
    acc = admin.get("/api/accounts").json()[0]
    assert (
        admin.post("/api/users", json={"username": "anna", "display_name": "Anna", "password": "geheim456"}).status_code
        == 201
    )

    anna = TestClient(app)
    anna.post("/api/auth/login", json={"username": "anna", "password": "geheim456"})
    assert len(anna.get("/api/accounts").json()) == 1
    assert (
        anna.post("/api/users", json={"username": "x1", "display_name": "X", "password": "geheim789"}).status_code
        == 403
    )

    admin.patch(f"/api/accounts/{acc['id']}", json={"shared": False})
    assert anna.get("/api/accounts").json() == []
    assert anna.get("/api/transactions").json()["total"] == 0
    assert anna.get("/api/overview", params={"month": "2026-11"}).json()["expenses"] == "0.00"


def test_category_crud(admin):
    wohnen = find_category(admin, "Wohnen")
    r = admin.post("/api/categories", json={"name": "Müllabfuhr", "parent_id": wohnen})
    assert r.status_code == 201
    sub = r.json()
    assert sub["kind"] == "expense"
    assert admin.post("/api/categories", json={"name": "Tiefer", "parent_id": sub["id"]}).status_code == 400
    assert admin.post("/api/categories", json={"name": "Müllabfuhr", "parent_id": wohnen}).status_code == 409
    response = admin.delete(f"/api/categories/{sub['id']}")
    assert response.status_code == 204
