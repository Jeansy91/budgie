"""CSV exports of other banks. The sample files are made up, modeled on each bank's export layout."""

import json
from datetime import date
from decimal import Decimal

import pytest

from app.importers import bank_csv

from .conftest import DATA

CSV = DATA / "csv"
IBAN = "DE89370400440532013000"


@pytest.mark.parametrize(
    "filename, format_id, iban",
    [
        ("sparkasse_camt.csv", "sparkasse", IBAN),
        ("volksbank.csv", "vr", IBAN),
        ("dkb.csv", "dkb", IBAN),
        ("dkb_legacy.csv", "dkb_legacy", IBAN),
        ("comdirect.csv", "comdirect", None),
        ("commerzbank.csv", "commerzbank", IBAN),
        ("deutsche_bank.csv", "deutsche_bank", IBAN),
        ("n26.csv", "n26", None),
    ],
)
def test_builtin_formats(filename, format_id, iban):
    raw = (CSV / filename).read_bytes()
    fmt, table, header_row = bank_csv.detect(raw)
    assert fmt.id == format_id
    s = bank_csv.parse(raw, fmt, table, header_row)
    assert s.iban == iban
    # Pending transactions are left out, the rest is sorted oldest first
    salary, *_, rewe = s.transactions
    assert salary.booking_date == date(2026, 10, 30) and salary.amount == Decimal("3200.00")
    assert rewe.booking_date == date(2026, 11, 14) and rewe.amount == Decimal("-54.32")
    if format_id != "commerzbank":  # Commerzbank has no separate payee column
        assert salary.payee == "Arbeitgeber AG" and rewe.payee == "REWE Markt GmbH"
        assert salary.purpose == "Gehalt Oktober 2026"
    assert len({t.dedup_hash for t in s.transactions}) == len(s.transactions)


def test_sparkasse_details():
    raw = (CSV / "sparkasse_camt.csv").read_bytes()
    s = bank_csv.parse(raw, bank_csv.FORMATS_BY_ID["sparkasse"])
    assert len(s.transactions) == 3  # the pending bakery payment is skipped
    rewe = s.transactions[-1]
    assert rewe.counterparty_iban == "DE02120300000000202051"
    assert rewe.counterparty_bic == "BYLADEM1001"
    assert rewe.creditor_id == "DE12ZZZ00000012345" and rewe.mandate_id == "M-9876"
    assert rewe.end_to_end_ref == "E2E-REWE-1"
    assert s.transactions[0].end_to_end_ref is None  # NOTPROVIDED


def test_comdirect_reads_only_the_first_account():
    s = bank_csv.parse((CSV / "comdirect.csv").read_bytes(), bank_csv.FORMATS_BY_ID["comdirect"])
    assert [t.amount for t in s.transactions] == [Decimal("3200.00"), Decimal("-54.32")]
    assert s.transactions[0].counterparty_iban == "DE75512108001245126199"


def test_ing_still_uses_its_own_parser(sample_csv):
    fmt, _, _ = bank_csv.detect(sample_csv)
    assert fmt.id == "ing" and fmt.source == "ing_csv"
    assert len(bank_csv.parse(sample_csv, fmt).transactions) == 7


def test_unknown_layout_preview_and_custom_mapping():
    raw = (CSV / "unknown.csv").read_bytes()
    assert bank_csv.detect(raw) is None
    p = bank_csv.preview(raw)
    assert p["delimiter"] == ";" and p["header_row"] == 1
    assert p["suggestion"]["columns"] == {
        "booking_date": 0,
        "value_date": 1,
        "payee": 2,
        "purpose": 3,
        "debit": 4,
        "credit": 5,
        "balance": 6,
    }
    mapping = bank_csv.CustomMapping(delimiter=";", header_row=1, columns=p["suggestion"]["columns"])
    s = bank_csv.parse_custom(raw, mapping)
    assert [t.amount for t in s.transactions] == [Decimal("3200.00"), Decimal("-54.32")]
    assert s.transactions[1].balance_after == Decimal("2345.67")


@pytest.mark.parametrize(
    "value, decimal, expected",
    [
        ("-1.234,56", "comma", "-1234.56"),
        ("1.234,56-", "comma", "-1234.56"),
        ("12,00 €", "comma", "12.00"),
        ("-1,234.56", "point", "-1234.56"),
        ("+3.50", "point", "3.50"),
    ],
)
def test_parse_amount(value, decimal, expected):
    assert bank_csv.parse_amount(value, decimal) == Decimal(expected)


def test_sniff_delimiter():
    assert bank_csv.sniff_delimiter("a,b,c\n1,2,3\n") == ","
    assert bank_csv.sniff_delimiter("a;b;c\n1,5;2;3\n") == ";"


# --- API --------------------------------------------------------------------


def upload(client, filename, **form):
    return client.post(
        "/api/imports/csv", files={"file": (filename, (CSV / filename).read_bytes(), "text/csv")}, data=form
    )


def test_import_detects_bank_and_creates_account(admin):
    r = upload(admin, "sparkasse_camt.csv")
    assert r.status_code == 201, r.text
    assert r.json()["format_name"] == "Sparkasse" and r.json()["account_created"] is True
    assert r.json()["rows_imported"] == 3
    [account] = admin.get("/api/accounts").json()
    assert account["iban"] == IBAN and account["bank"] == "Sparkasse"
    # Same file again: everything is a duplicate
    assert upload(admin, "sparkasse_camt.csv").json()["rows_duplicate"] == 3


def test_import_without_iban_needs_an_account(admin):
    r = upload(admin, "n26.csv")
    assert r.status_code == 400 and "IBAN" in r.json()["detail"]
    account = admin.post("/api/accounts", json={"name": "N26", "bank": "N26"}).json()
    r = upload(admin, "n26.csv", account_id=str(account["id"]))
    assert r.status_code == 201 and r.json()["rows_imported"] == 2


def test_ing_via_generic_endpoint(admin, sample_csv):
    r = admin.post("/api/imports/csv", files={"file": ("u.csv", sample_csv, "text/csv")})
    assert r.json()["format_name"] == "ING" and r.json()["rows_imported"] == 7
    # The old ING endpoint shares the source, so nothing is imported twice
    r = admin.post("/api/imports/ing-csv", files={"file": ("u.csv", sample_csv, "text/csv")})
    assert r.json()["rows_duplicate"] == 7


def test_unknown_format_mapping_is_saved(admin):
    r = upload(admin, "unknown.csv")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_format"

    preview = admin.post(
        "/api/imports/csv/preview", files={"file": ("u.csv", (CSV / "unknown.csv").read_bytes(), "text/csv")}
    ).json()
    assert preview["format_name"] is None and preview["columns"][0] == "Datum"

    account = admin.post("/api/accounts", json={"name": "Musterbank", "bank": "Musterbank"}).json()
    mapping = {"delimiter": ";", "header_row": 1, **preview["suggestion"]}
    r = upload(admin, "unknown.csv", account_id=str(account["id"]), mapping=json.dumps(mapping), save_as="Musterbank")
    assert r.status_code == 201, r.text
    assert r.json()["rows_imported"] == 2

    # Next time the saved mapping recognizes the file
    r = upload(admin, "unknown.csv", account_id=str(account["id"]))
    assert r.status_code == 201 and r.json()["format_name"] == "Musterbank" and r.json()["rows_duplicate"] == 2
    [profile] = admin.get("/api/imports/csv/profiles").json()
    response = admin.delete(f"/api/imports/csv/profiles/{profile['id']}")
    assert response.status_code == 204
    assert upload(admin, "unknown.csv").status_code == 422


def test_invalid_mapping(admin):
    bad = {"delimiter": ";", "header_row": 1, "columns": {"payee": 2}}
    r = upload(admin, "unknown.csv", mapping=json.dumps(bad))
    assert r.status_code == 400 and "Buchungsdatum" in r.json()["detail"]
    assert upload(admin, "unknown.csv", mapping="kein json").status_code == 400


def test_formats_list(admin):
    ids = [f["id"] for f in admin.get("/api/imports/csv/formats").json()]
    assert ids[0] == "ing" and "sparkasse" in ids and "n26" in ids
