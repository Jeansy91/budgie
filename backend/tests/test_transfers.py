"""Transfers between own accounts: detection, settings and the hide filter."""

from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.db import SessionLocal
from app.importers.common import ParsedTransaction
from app.importers.store import store_transactions
from app.models import Account, User
from app.transfers import is_valid_iban

from .conftest import find_category

IBAN_A = "DE89 3704 0044 0532 0130 00"
IBAN_B = "DE02 1203 0000 0000 2020 51"
IBAN_EXTRA = "GB82 WEST 1234 5698 7654 32"
IBAN_FOREIGN = "FR14 2004 1010 0505 0001 3M02 606"


def parsed(payee: str, amount: str, iban: str | None, day: int = 5, purpose: str = "") -> ParsedTransaction:
    return ParsedTransaction(
        booking_date=date(2026, 11, day),
        value_date=None,
        payee=payee,
        booking_text="Ueberweisung",
        purpose=purpose or payee,
        amount=Decimal(amount),
        currency="EUR",
        balance_after=None,
        dedup_hash=f"{payee}-{amount}-{day}-{purpose}",
        counterparty_iban=iban,
    )


def store(account_id: int, *rows: ParsedTransaction) -> None:
    """Imports transactions like the FinTS sync does."""
    with SessionLocal() as db:
        account = db.get(Account, account_id)
        user = db.scalars(select(User)).first()
        assert account is not None and user is not None
        store_transactions(
            db, household_id=user.household_id, user_id=user.id, account=account, parsed=list(rows), source="fints"
        )
        db.commit()


def make_accounts(client) -> tuple[int, int]:
    a = client.post("/api/accounts", json={"name": "Giro", "iban": IBAN_A}).json()["id"]
    b = client.post("/api/accounts", json={"name": "Tagesgeld", "iban": IBAN_B}).json()["id"]
    return a, b


def items(client, **params) -> dict[str, dict]:
    return {t["payee"]: t for t in client.get("/api/transactions", params=params).json()["items"]}


def test_iban_checksum():
    assert is_valid_iban("DE89370400440532013000")
    assert is_valid_iban("GB82WEST12345698765432")
    assert not is_valid_iban("DE89370400440532013001")
    assert not is_valid_iban("DE8")
    assert not is_valid_iban("1234567890123456")


def test_detects_transfer_on_import(admin, no_ai):
    a, _ = make_accounts(admin)
    store(a, parsed("Umbuchung", "-100.00", IBAN_B.replace(" ", "").lower()), parsed("REWE", "-5.00", IBAN_FOREIGN))
    got = items(admin)
    target = find_category(admin, "Umbuchungen", "Transfers zwischen eigenen Konten")
    assert got["Umbuchung"]["category_id"] == target
    assert got["Umbuchung"]["category_source"] == "transfer"
    assert got["REWE"]["category_source"] is None
    assert admin.get("/api/transfers/settings").json()["detected_count"] == 1


def test_own_iban_is_not_a_transfer(admin, no_ai):
    a, _ = make_accounts(admin)
    store(a, parsed("Selbst", "-1.00", IBAN_A))
    assert items(admin)["Selbst"]["category_source"] is None


def test_extra_iban(admin, no_ai):
    a, _ = make_accounts(admin)
    store(a, parsed("Sparkonto", "-50.00", IBAN_EXTRA))
    assert items(admin)["Sparkonto"]["category_source"] is None
    r = admin.put(
        "/api/transfers/settings", json={"auto_detect": True, "extra_ibans": [IBAN_EXTRA, IBAN_EXTRA.lower()]}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["extra_ibans"] == ["GB82WEST12345698765432"] and body["changed"] == 1
    assert items(admin)["Sparkonto"]["category_source"] == "transfer"
    # Removing the IBAN un-marks the transaction again
    body = admin.put("/api/transfers/settings", json={"auto_detect": True, "extra_ibans": []}).json()
    assert body["changed"] == 1
    assert items(admin)["Sparkonto"]["category_id"] is None


def test_manual_assignment_is_never_overwritten(admin, no_ai):
    a, _ = make_accounts(admin)
    food = find_category(admin, "Lebensmittel", "Supermarkt")
    store(a, parsed("Umbuchung", "-100.00", None))
    tid = items(admin)["Umbuchung"]["id"]
    assert admin.patch(f"/api/transactions/{tid}", json={"category_id": food}).status_code == 200
    with SessionLocal() as db:
        from app.models import Transaction

        db.get(Transaction, tid).counterparty_iban = IBAN_B.replace(" ", "")  # type: ignore[union-attr]
        db.commit()
    assert admin.put("/api/transfers/settings", json={"auto_detect": True, "extra_ibans": []}).json()["changed"] == 0
    t = items(admin)["Umbuchung"]
    assert (t["category_id"], t["category_source"]) == (food, "manual")


def test_setting_off_unmarks_and_recategorizes(admin, no_ai):
    a, _ = make_accounts(admin)
    food = find_category(admin, "Lebensmittel", "Supermarkt")
    admin.post(
        "/api/rules", json={"category_id": food, "field": "payee", "match_type": "contains", "pattern": "Umbuchung"}
    )
    store(a, parsed("Umbuchung", "-100.00", IBAN_B))
    # The IBAN match beats the rule
    assert items(admin)["Umbuchung"]["category_source"] == "transfer"
    body = admin.put("/api/transfers/settings", json={"auto_detect": False, "extra_ibans": []}).json()
    assert body["changed"] == 1 and body["detected_count"] == 0
    t = items(admin)["Umbuchung"]
    assert (t["category_id"], t["category_source"]) == (food, "rule")
    # Turning it on again marks it as transfer
    admin.put("/api/transfers/settings", json={"auto_detect": True, "extra_ibans": []})
    assert items(admin)["Umbuchung"]["category_source"] == "transfer"


def test_new_account_detects_earlier_transfers_and_delete_unmarks(admin, no_ai):
    a = admin.post("/api/accounts", json={"name": "Giro", "iban": IBAN_A}).json()["id"]
    store(a, parsed("Umbuchung", "-100.00", IBAN_B))
    assert items(admin)["Umbuchung"]["category_source"] is None
    b = admin.post("/api/accounts", json={"name": "Tagesgeld", "iban": IBAN_B}).json()["id"]
    assert items(admin)["Umbuchung"]["category_source"] == "transfer"
    response = admin.delete(f"/api/accounts/{b}")
    assert response.status_code == 204
    assert items(admin)["Umbuchung"]["category_source"] is None


def test_hide_transfers_filter(admin, no_ai):
    a, _ = make_accounts(admin)
    manual_transfer = find_category(admin, "Umbuchungen", "Transfers zwischen eigenen Konten")
    store(
        a,
        parsed("Auto", "-100.00", IBAN_B, day=1),
        parsed("Manuell", "-20.00", None, day=2),
        parsed("Normal", "-5.00", None, day=3),
    )
    tid = items(admin)["Manuell"]["id"]
    admin.patch(f"/api/transactions/{tid}", json={"category_id": manual_transfer})
    assert set(items(admin)) == {"Auto", "Manuell", "Normal"}
    page = admin.get("/api/transactions", params={"hide_transfers": True}).json()
    assert {t["payee"] for t in page["items"]} == {"Normal"} and page["total"] == 1
    # Main category of kind transfer counts as well
    main = find_category(admin, "Umbuchungen")
    nid = items(admin)["Normal"]["id"]
    admin.patch(f"/api/transactions/{nid}", json={"category_id": main})
    assert items(admin, hide_transfers=True) == {}


def test_invalid_iban_rejected(admin):
    r = admin.put("/api/transfers/settings", json={"auto_detect": True, "extra_ibans": ["DE89 3704 0044 0532 0130 01"]})
    assert r.status_code == 400
    assert "DE89 3704 0044 0532 0130 01" in r.json()["detail"]
    assert admin.get("/api/transfers/settings").json()["extra_ibans"] == []


def test_settings_lists_account_ibans(admin):
    make_accounts(admin)
    s = admin.get("/api/transfers/settings").json()
    assert s["auto_detect"] is True
    assert [(x["name"], x["iban"]) for x in s["account_ibans"]] == [
        ("Giro", IBAN_A.replace(" ", "")),
        ("Tagesgeld", IBAN_B.replace(" ", "")),
    ]


def test_overview_totals_unaffected(admin, no_ai):
    a, _ = make_accounts(admin)
    for payee, sub in (("Arbeitgeber", ("Einnahmen", "Gehalt")), ("REWE", ("Lebensmittel", "Supermarkt"))):
        rule = {"category_id": find_category(admin, *sub), "field": "payee", "match_type": "contains", "pattern": payee}
        admin.post("/api/rules", json=rule)
    store(
        a,
        parsed("Umbuchung", "-100.00", IBAN_B),
        parsed("Arbeitgeber", "2000.00", IBAN_FOREIGN, day=2),
        parsed("REWE", "-30.00", None, day=3),
    )
    o = admin.get("/api/overview", params={"month": "2026-11"}).json()
    assert Decimal(str(o["income"])) == Decimal("2000.00")
    assert Decimal(str(o["expenses"])) == Decimal("30.00")
    assert Decimal(str(o["transfers"])) == Decimal("-100.00")
