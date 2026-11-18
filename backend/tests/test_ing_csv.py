from decimal import Decimal

import pytest

from app.importers import ing_csv


def test_parse_header_and_rows(sample_csv):
    s = ing_csv.parse(sample_csv)
    assert s.iban == "DE89370400440532013000"
    assert s.account_name == "Girokonto"
    assert len(s.transactions) == 7
    # sorted chronologically, oldest first
    assert s.transactions[0].payee == "Max Mustermann"
    assert s.transactions[-1].payee == "REWE Markt GmbH"
    gehalt = next(t for t in s.transactions if t.payee == "Arbeitgeber AG")
    assert gehalt.amount == Decimal("3200.00")
    assert gehalt.balance_after == Decimal("3443.99")
    assert gehalt.currency == "EUR"


def test_identical_rows_get_distinct_hashes(sample_csv):
    s = ing_csv.parse(sample_csv)
    hashes = [t.dedup_hash for t in s.transactions]
    assert len(set(hashes)) == len(hashes)


def test_cp1252_and_old_valuta_column(sample_csv):
    text = sample_csv.decode().replace("Wertstellungsdatum", "Valuta")
    s = ing_csv.parse(text.encode("cp1252"))
    assert any(t.payee == "Bäckerei Schmidt" for t in s.transactions)
    assert s.transactions[0].value_date is not None


def test_extra_category_column(sample_csv):
    lines = sample_csv.decode().splitlines()
    out = []
    for line in lines:
        cells = line.split(";")
        if cells[0] == "Buchung":
            cells.insert(4, "Kategorie")
        elif len(cells) == 9 and cells[0][:2].isdigit():
            cells.insert(4, "Lebensmittel")
        out.append(";".join(cells))
    s = ing_csv.parse("\n".join(out).encode())
    rewe = next(t for t in s.transactions if t.payee.startswith("REWE"))
    assert rewe.purpose == "REWE SAGT DANKE 12345"
    assert rewe.amount == Decimal("-54.32")


def test_rejects_other_files():
    with pytest.raises(ing_csv.IngCsvError):
        ing_csv.parse(b"Datum,Betrag\n01.01.2026,5")


def test_bad_amount_reports_line(sample_csv):
    broken = sample_csv.decode().replace("-54,32", "abc").encode()
    with pytest.raises(ing_csv.IngCsvError, match="Zeile"):
        ing_csv.parse(broken)
