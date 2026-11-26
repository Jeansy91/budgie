import json

import httpx
import pytest

from app.ai import llm
from app.config import get_settings

from .conftest import find_category
from .test_api import upload

HEADER = """Umsatzanzeige;Datei erstellt am: 16.11.2026 10:15
;Letztes Update: aktuell

IBAN;DE89 3704 0044 0532 0130 00
Kontoname;Girokonto
Bank;ING
Kunde;Max Mustermann
Zeitraum;01.10.2026 - 16.11.2026
Saldo;2.345,67;EUR

Sortierung;Datum absteigend

Buchung;Wertstellungsdatum;Auftraggeber/Empfänger;Buchungstext;Verwendungszweck;Saldo;Währung;Betrag;Währung
"""


def csv(*rows: tuple[str, str, str, str, str]) -> bytes:
    """rows: (date, payee, booking text, purpose, amount)"""
    lines = [f"{d};{d};{payee};{bt};{purpose};1.000,00;EUR;{amount};EUR" for d, payee, bt, purpose, amount in rows]
    return (HEADER + "\n".join(lines) + "\n").encode("utf-8")


def transactions(client, **params):
    return client.get("/api/transactions", params=params).json()["items"]


def by_payee(client, payee):
    return next(t for t in transactions(client) if t["payee"] == payee)


def test_categorizes_known_payees_from_start(admin, sample_csv):
    r = upload(admin, sample_csv)
    assert r.status_code == 201
    rewe = by_payee(admin, "REWE Markt GmbH")
    assert rewe["category_id"] == find_category(admin, "Lebensmittel", "Supermarkt")
    assert rewe["category_source"] == "model"
    assert 0.6 <= rewe["category_confidence"] <= 1
    assert r.json()["rows_categorized"] >= 1


def test_learns_from_corrections(admin):
    hund = find_category(admin, "Kinder und Haustiere", "Tierbedarf/Tierarzt")
    upload(
        admin,
        csv(
            ("02.10.2026", "Hundesalon Fiffi", "Lastschrift", "Scheren und Baden", "-45,00"),
            ("16.10.2026", "Hundesalon Fiffi", "Lastschrift", "Krallen schneiden", "-25,00"),
        ),
    )
    first = by_payee(admin, "Hundesalon Fiffi")
    assert first["category_id"] != hund

    # Two corrections are enough for new transactions to land in the right place
    for t in transactions(admin):
        r = admin.patch(f"/api/transactions/{t['id']}", json={"category_id": hund})
        assert r.json()["transaction"]["category_source"] == "manual"

    upload(admin, csv(("05.11.2026", "Hundesalon Fiffi", "Lastschrift", "Scheren", "-40,00")))
    new = next(t for t in transactions(admin) if t["booking_date"] == "2026-11-05")
    assert new["category_id"] == hund
    assert new["category_source"] == "model"

    status = admin.get("/api/ai/status").json()
    assert status["model"]["corrections"] == 2
    assert status["ai_categorized"] >= 1


def test_rules_beat_ai_and_manual_beats_everything(admin, sample_csv):
    upload(admin, sample_csv)
    rewe = by_payee(admin, "REWE Markt GmbH")
    assert rewe["category_source"] == "model"

    getraenke = find_category(admin, "Lebensmittel", "Getränke")
    r = admin.post("/api/rules", json={"category_id": getraenke, "pattern": "REWE"})
    assert r.status_code == 201
    admin.post("/api/rules/apply", json={})
    assert by_payee(admin, "REWE Markt GmbH")["category_source"] == "rule"

    strom = by_payee(admin, "Stadtwerke Musterstadt")
    gas = find_category(admin, "Wohnen", "Gas/Heizung")
    admin.patch(f"/api/transactions/{strom['id']}", json={"category_id": gas})
    admin.post("/api/ai/recategorize", json={})
    after = by_payee(admin, "Stadtwerke Musterstadt")
    assert after["category_id"] == gas and after["category_source"] == "manual"


def test_debits_never_get_income_categories(admin):
    income = {
        c["id"] for main in admin.get("/api/categories").json() if main["kind"] == "income" for c in main["children"]
    }
    upload(admin, csv(("02.10.2026", "Arbeitgeber AG", "Lastschrift", "Rueckforderung Gehalt", "-120,00")))
    t = transactions(admin)[0]
    assert t["category_id"] not in income
    assert t["suggested_category_id"] not in income


def test_unsure_cases_become_suggestions(admin, monkeypatch):
    monkeypatch.setattr(get_settings(), "ai_auto_threshold", 0.999)
    upload(admin, csv(("02.10.2026", "REWE Markt", "Lastschrift", "Einkauf", "-17,00")))
    t = transactions(admin)[0]
    assert t["category_id"] is None
    assert t["suggested_category_id"] is not None
    assert 0 < t["suggestion_confidence"] < 0.999

    review = transactions(admin, ai_review=True)
    assert [x["id"] for x in review] == [t["id"]]

    # Accepting a suggestion with one click turns it into a manual assignment
    r = admin.patch(f"/api/transactions/{t['id']}", json={"category_id": t["suggested_category_id"]})
    done = r.json()["transaction"]
    assert done["category_source"] == "manual"
    assert done["suggested_category_id"] is None
    assert transactions(admin, ai_review=True) == []


def test_train_endpoint_and_status(admin, sample_csv):
    status = admin.get("/api/ai/status").json()
    assert status["model"] is None
    assert status["llm"]["configured"] is False
    upload(admin, sample_csv)
    status = admin.post("/api/ai/train").json()
    assert status["model"]["classes"] > 10
    assert status["enabled"] is True


@pytest.fixture
def fake_ollama(monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_url", "http://ollama:11434")
    monkeypatch.setattr(get_settings(), "ai_auto_threshold", 0.999)
    calls = []

    def post(url, json=None, timeout=None):
        calls.append(json)
        enum = json["format"]["properties"]["kategorie"]["enum"]
        assert "Freizeit › Hobbys" in enum
        assert not any(label.startswith("Einnahmen") for label in enum)  # Debit
        content = '{"kategorie": "Freizeit › Hobbys"}'
        return httpx.Response(200, json={"message": {"content": content}}, request=httpx.Request("POST", url))

    def get(url, timeout=None):
        return httpx.Response(200, json={"models": [{"name": "qwen2.5:7b"}]}, request=httpx.Request("GET", url))

    monkeypatch.setattr(llm.httpx, "post", post)
    monkeypatch.setattr(llm.httpx, "get", get)
    return calls


def test_llm_handles_unsure_cases(admin, fake_ollama):
    upload(admin, csv(("02.10.2026", "Modellbau Krause", "Lastschrift", "Bausatz Lokomotive", "-79,00")))
    t = transactions(admin)[0]
    assert t["category_id"] == find_category(admin, "Freizeit", "Hobbys")
    assert t["category_source"] == "llm"
    assert len(fake_ollama) == 1
    prompt = fake_ollama[0]["messages"][1]["content"]
    assert "Modellbau Krause" in prompt

    status = admin.get("/api/ai/status").json()["llm"]
    assert status["configured"] and status["reachable"] and status["model_available"]


def test_llm_errors_do_not_break_import(admin, monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_url", "http://ollama:11434")
    monkeypatch.setattr(get_settings(), "ai_auto_threshold", 0.999)

    def post(url, json=None, timeout=None):
        raise httpx.ConnectError("keine Verbindung")

    monkeypatch.setattr(llm.httpx, "post", post)
    r = upload(admin, csv(("02.10.2026", "Modellbau Krause", "Lastschrift", "Bausatz", "-79,00")))
    assert r.status_code == 201
    t = transactions(admin)[0]
    assert t["category_id"] is None


def test_unknown_payees_get_no_guess(admin):
    upload(admin, csv(("02.10.2026", "Irgendwas Unbekanntes KG", "Lastschrift", "Rechnung", "-17,00")))
    t = transactions(admin)[0]
    assert t["category_id"] is None and t["suggested_category_id"] is None


def test_llm_rejects_unknown_labels(monkeypatch):
    monkeypatch.setattr(get_settings(), "ollama_url", "http://ollama:11434")

    def post(url, json=None, timeout=None):
        return httpx.Response(
            200,
            json={"message": {"content": json_dumps({"kategorie": "Erfunden"})}},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(llm.httpx, "post", post)
    with pytest.raises(llm.LlmError):
        llm.classify(llm.TxText("A", "B", "C", -1), ["Wohnen › Strom"])


def json_dumps(value) -> str:
    return json.dumps(value)
