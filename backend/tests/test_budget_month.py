"""Budget month: end-of-month salary counts towards the following month."""

from datetime import date

from app.budget_month import first_of_next_month, in_month_end

from .conftest import find_category
from .test_api import upload

HEADER = """Umsatzanzeige;Datei erstellt am: 16.11.2026 10:15
;Letztes Update: aktuell

IBAN;DE89 3704 0044 0532 0130 00
Kontoname;Girokonto
Bank;ING
Kunde;Max Mustermann
Zeitraum;01.09.2026 - 16.11.2026
Saldo;2.345,67;EUR

Sortierung;Datum absteigend

Buchung;Wertstellungsdatum;Auftraggeber/Empfänger;Buchungstext;Verwendungszweck;Saldo;Währung;Betrag;Währung
"""


def csv(*rows: tuple[str, str, str, str, str]) -> bytes:
    """rows: (date, payer, booking text, purpose, amount)"""
    lines = [f"{d};{d};{p};{bt};{vz};1.000,00;EUR;{amt};EUR" for d, p, bt, vz, amt in rows]
    return (HEADER + "\n".join(lines) + "\n").encode("latin-1")


def by_payee(client, month: str | None = None) -> dict[str, dict]:
    """Newest transaction per payer"""
    items = client.get("/api/transactions", params={"month": month} if month else {}).json()["items"]
    return {t["payee"]: t for t in reversed(items)}


def test_helpers():
    assert first_of_next_month(date(2026, 12, 30)) == date(2027, 1, 1)
    assert in_month_end(date(2026, 10, 25), 7) and not in_month_end(date(2026, 10, 24), 7)
    assert in_month_end(date(2026, 2, 22), 7) and not in_month_end(date(2026, 2, 21), 7)


def test_salary_booking_text_shifts_to_next_month(admin, sample_csv):
    upload(admin, sample_csv)
    t = by_payee(admin)["Arbeitgeber AG"]
    assert t["booking_date"] == "2026-10-30"
    assert t["budget_date"] == "2026-11-01"
    assert t["budget_shift"] is None
    assert "Arbeitgeber AG" in by_payee(admin, "2026-11")
    assert "Arbeitgeber AG" not in by_payee(admin, "2026-10")

    s = admin.get("/api/budget-month/settings").json()
    assert s["salary_shift_enabled"] and s["salary_shift_days"] == 7 and s["shifted_count"] == 1
    assert s["salary_category_ids"] == [find_category(admin, "Einnahmen", "Gehalt")]


def test_disable_and_threshold(admin):
    gehalt = find_category(admin, "Einnahmen", "Gehalt")
    upload(admin, csv(("22.10.2026", "Arbeitgeber AG", "Gehalt/Rente", "Gehalt Oktober", "3.000,00")))
    assert by_payee(admin)["Arbeitgeber AG"]["budget_date"] == "2026-10-22"  # 10 days before the end of the month

    settings = {
        "salary_shift_enabled": True,
        "salary_shift_days": 10,
        "salary_category_ids": [gehalt],
        "salary_payees": [],
        "salary_auto_detect": True,
    }
    r = admin.put("/api/budget-month/settings", json=settings)
    assert r.status_code == 200, r.text
    assert r.json()["shifted_count"] == 1
    assert by_payee(admin)["Arbeitgeber AG"]["budget_date"] == "2026-11-01"

    r = admin.put("/api/budget-month/settings", json={**settings, "salary_shift_enabled": False})
    assert r.json()["shifted_count"] == 0
    assert by_payee(admin)["Arbeitgeber AG"]["budget_date"] == "2026-10-22"


def test_manual_override(admin, sample_csv):
    upload(admin, sample_csv)
    items = by_payee(admin)
    salary, rewe = items["Arbeitgeber AG"], items["REWE Markt GmbH"]

    r = admin.patch(f"/api/transactions/{salary['id']}", json={"budget_shift": "same"})
    assert r.status_code == 200, r.text
    assert r.json()["transaction"]["budget_date"] == "2026-10-30"
    assert r.json()["transaction"]["budget_shift"] == "same"

    # An expense can also be moved to the following month on purpose
    r = admin.patch(f"/api/transactions/{rewe['id']}", json={"budget_shift": "next"})
    assert r.json()["transaction"]["budget_date"] == "2026-12-01"

    r = admin.patch(f"/api/transactions/{salary['id']}", json={"budget_shift": "auto"})
    assert r.json()["transaction"]["budget_date"] == "2026-11-01"
    assert r.json()["transaction"]["budget_shift"] is None


def test_recurring_payer_is_detected(admin):
    upload(
        admin,
        csv(
            ("28.10.2026", "Firma Beispiel GmbH", "Ueberweisung", "Lohn 10/2026", "2.480,00"),
            ("27.10.2026", "Oma Erna", "Ueberweisung", "Geburtstag", "500,00"),
            ("29.09.2026", "Firma Beispiel GmbH", "Ueberweisung", "Lohn 09/2026", "2.450,00"),
        ),
    )
    items = by_payee(admin)
    assert items["Firma Beispiel GmbH"]["budget_date"] == "2026-11-01"
    assert items["Oma Erna"]["budget_date"] == "2026-10-27"
    okt = admin.get("/api/transactions", params={"month": "2026-10"}).json()["items"]
    assert [t["purpose"] for t in okt if t["payee"] == "Firma Beispiel GmbH"] == ["Lohn 09/2026"]

    # Without auto-detection, only category and payer patterns apply
    gehalt = find_category(admin, "Einnahmen", "Gehalt")
    admin.put(
        "/api/budget-month/settings",
        json={
            "salary_shift_days": 7,
            "salary_category_ids": [gehalt],
            "salary_payees": ["oma"],
            "salary_auto_detect": False,
        },
    )
    items = by_payee(admin)
    assert items["Firma Beispiel GmbH"]["budget_date"] == "2026-10-28"
    assert items["Oma Erna"]["budget_date"] == "2026-11-01"


def test_category_decides(admin):
    upload(
        admin,
        csv(
            ("29.10.2026", "Arbeitgeber AG", "Gehalt/Rente", "Gehalt Oktober", "3.000,00"),
            ("30.10.2026", "Versicherung AG", "Gutschrift", "Erstattung", "1.200,00"),
        ),
    )
    items = by_payee(admin)
    assert items["Arbeitgeber AG"]["budget_date"] == "2026-11-01"
    assert items["Versicherung AG"]["budget_date"] == "2026-10-30"

    # Different income category: no longer moved
    sonstige = find_category(admin, "Einnahmen", "Sonstige Einnahmen")
    r = admin.patch(f"/api/transactions/{items['Arbeitgeber AG']['id']}", json={"category_id": sonstige})
    assert r.json()["transaction"]["budget_date"] == "2026-10-29"

    # Salary category: moved, even without booking text
    gehalt = find_category(admin, "Einnahmen", "Gehalt")
    r = admin.patch(f"/api/transactions/{items['Versicherung AG']['id']}", json={"category_id": gehalt})
    assert r.json()["transaction"]["budget_date"] == "2026-11-01"

    # Transfers are never moved automatically
    transfer = find_category(admin, "Umbuchungen", "Transfers zwischen eigenen Konten")
    r = admin.patch(f"/api/transactions/{items['Versicherung AG']['id']}", json={"category_id": transfer})
    assert r.json()["transaction"]["budget_date"] == "2026-10-30"


def test_unknown_category_rejected(admin):
    r = admin.put("/api/budget-month/settings", json={"salary_category_ids": [99999]})
    assert r.status_code == 400
