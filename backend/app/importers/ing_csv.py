"""Parser for the "Umsatzanzeige" CSV export from ING online banking.

File layout (semicolon separated, German number and date formats):

    Umsatzanzeige;Datei erstellt am: 16.11.2026 10:00
    ;Letztes Update: aktuell

    IBAN;DE12 3456 7890 1234 5678 90
    Kontoname;Girokonto
    Bank;ING
    ...
    Buchung;Wertstellungsdatum;Auftraggeber/Empfänger;Buchungstext;Verwendungszweck;Saldo;Währung;Betrag;Währung
    14.11.2026;14.11.2026;REWE Markt GmbH;Lastschrift;...;1.234,56;EUR;-12,34;EUR

Older exports name the second column "Valuta", newer ones contain an
additional "Kategorie" column. Columns are therefore mapped by their header,
not by their position.
"""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..i18n import t

# Re-exported for code that imported them from here before other banks were supported
from .common import (  # noqa: F401
    CsvError,
    ParsedStatement,
    ParsedTransaction,
    assign_fingerprints,
    decode,
    fingerprint,
    normalize_iban,
)


class IngCsvError(CsvError):
    pass


def parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise IngCsvError(t("csv.invalid_amount", value=repr(value))) from exc


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except ValueError as exc:
        raise IngCsvError(t("csv.invalid_date", value=repr(value))) from exc


_HEADER_ALIASES = {
    "buchung": "booking_date",
    "buchungsdatum": "booking_date",
    "wertstellungsdatum": "value_date",
    "valuta": "value_date",
    "auftraggeber/empfänger": "payee",
    "buchungstext": "booking_text",
    "verwendungszweck": "purpose",
    "saldo": "balance",
    "betrag": "amount",
}


def _map_header(header: list[str]) -> dict[str, int]:
    """Maps column names. "Währung" appears twice: after "Saldo" and after "Betrag"."""
    mapping: dict[str, int] = {}
    previous = None
    for idx, name in enumerate(header):
        key = name.strip().lower()
        if key == "währung":
            if previous == "amount":
                mapping["currency"] = idx
            elif previous == "balance":
                mapping["balance_currency"] = idx
        elif key in _HEADER_ALIASES:
            mapping.setdefault(_HEADER_ALIASES[key], idx)
        previous = _HEADER_ALIASES.get(key)
    missing = {"booking_date", "amount"} - mapping.keys()
    if missing:
        raise IngCsvError(t("csv.missing_columns", columns=", ".join(sorted(missing))))
    return mapping


def parse(raw: bytes) -> ParsedStatement:
    text = decode(raw)
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    statement = ParsedStatement()

    header_idx = None
    ascending = False  # ING default: newest transaction first
    for i, row in enumerate(rows):
        if not row:
            continue
        key = row[0].strip().lower()
        if key in ("buchung", "buchungsdatum") and len(row) > 3:
            header_idx = i
            break
        if len(row) > 1:
            if key == "iban":
                statement.iban = normalize_iban(row[1])
            elif key == "kontoname":
                statement.account_name = row[1].strip()
            elif key == "bank":
                statement.bank = row[1].strip()
            elif key == "sortierung":
                ascending = "aufsteigend" in row[1].lower()

    if header_idx is None:
        raise IngCsvError(t("csv.not_ing"))

    cols = _map_header(rows[header_idx])

    def get(row: list[str], name: str) -> str:
        idx = cols.get(name)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    for line_no, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        if not row or not any(cell.strip() for cell in row):
            continue
        try:
            value_date = get(row, "value_date")
            balance = get(row, "balance")
            statement.transactions.append(
                ParsedTransaction(
                    booking_date=parse_date(get(row, "booking_date")),
                    value_date=parse_date(value_date) if value_date else None,
                    payee=get(row, "payee"),
                    booking_text=get(row, "booking_text"),
                    purpose=get(row, "purpose"),
                    amount=parse_amount(get(row, "amount")),
                    currency=get(row, "currency") or "EUR",
                    balance_after=parse_amount(balance) if balance else None,
                )
            )
        except IngCsvError as exc:
            raise IngCsvError(t("csv.line", line=line_no, error=exc)) from exc

    # Store chronologically, oldest transaction first
    if not ascending:
        statement.transactions.reverse()
    statement.transactions.sort(key=lambda t: t.booking_date)

    assign_fingerprints(statement.transactions)
    return statement
