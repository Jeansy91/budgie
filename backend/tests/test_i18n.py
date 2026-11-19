from fastapi.testclient import TestClient

from app.i18n import MESSAGES, parse_accept_language
from app.main import app
from app.seed import DEFAULT_NAMES

EN = {"Accept-Language": "en"}


def test_parse_accept_language():
    assert parse_accept_language(None) == "de"
    assert parse_accept_language("en-US,en;q=0.9") == "en"
    assert parse_accept_language("fr-FR, en;q=0.5, de;q=0.8") == "de"
    assert parse_accept_language("fr, it") == "de"
    assert parse_accept_language("en;q=0, de") == "de"


def test_every_message_and_category_has_both_languages():
    for key, texts in MESSAGES.items():
        assert set(texts) == {"de", "en"}, key
    for key, names in DEFAULT_NAMES.items():
        assert names["de"] and names["en"], key


def test_default_categories_follow_request_language(admin):
    de = admin.get("/api/categories").json()
    en = admin.get("/api/categories", headers=EN).json()
    assert de[1]["name"] == "Lebensmittel" and en[1]["name"] == "Groceries"
    assert en[1]["children"][0]["name"] == "Supermarket"
    assert [c["id"] for c in de] == [c["id"] for c in en]


def test_renamed_and_own_categories_are_not_translated(admin):
    cats = admin.get("/api/categories", headers=EN).json()
    groceries = cats[1]
    # Saving the translated name unchanged keeps the category a default one
    admin.patch(f"/api/categories/{groceries['id']}", json={"name": "Groceries"}, headers=EN)
    assert admin.get("/api/categories").json()[1]["name"] == "Lebensmittel"

    admin.patch(f"/api/categories/{groceries['id']}", json={"name": "Food"}, headers=EN)
    own = admin.post("/api/categories", json={"name": "Haustier", "parent_id": groceries["id"]}).json()
    for headers in ({}, EN):
        main = admin.get("/api/categories", headers=headers).json()[1]
        assert main["name"] == "Food"
        assert main["children"][-1]["id"] == own["id"] and main["children"][-1]["name"] == "Haustier"


def test_error_messages_follow_request_language(admin):
    fresh = TestClient(app)
    body = {"username": "alex", "password": "falsch"}
    assert fresh.post("/api/auth/login", json=body).json()["detail"] == "Nutzername oder Passwort falsch"
    assert fresh.post("/api/auth/login", json=body, headers=EN).json()["detail"] == "Wrong username or password"
    assert admin.get("/api/transactions/999", headers=EN).json()["detail"] == "Transaction not found"


def test_overview_uncategorized_label(admin, sample_csv):
    admin.post("/api/imports/ing-csv", files={"file": ("u.csv", sample_csv, "text/csv")})
    tx = admin.get("/api/transactions").json()["items"][0]
    admin.patch(f"/api/transactions/{tx['id']}", json={"category_id": None})
    month = tx["budget_date"][:7]
    names = {c["name"] for c in admin.get("/api/overview", params={"month": month}, headers=EN).json()["expense_categories"]}
    names |= {c["name"] for c in admin.get("/api/overview", params={"month": month}, headers=EN).json()["income_categories"]}
    assert "Uncategorized" in names


def test_language_preference(admin):
    assert admin.get("/api/auth/me").json()["language"] is None
    assert admin.patch("/api/auth/me", json={"language": "en"}).json()["language"] == "en"
    assert admin.get("/api/auth/me").json()["language"] == "en"
    assert admin.patch("/api/auth/me", json={"language": "fr"}).status_code == 422
    assert admin.patch("/api/auth/me", json={"language": None}).json()["language"] is None
