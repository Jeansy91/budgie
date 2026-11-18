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
import hashlib
import io
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


class IngCsvError(ValueError):
    pass


@dataclass
class ParsedTransaction:
    booking_date: date
    value_date: date | None
    payee: str
    booking_text: str
    purpose: str
    amount: Decimal
    currency: str
    balance_after: Decimal | None
    dedup_hash: str = ""
    # SEPA details (only delivered by FinTS); not part of the fingerprint
    counterparty_iban: str | None = None
    counterparty_bic: str | None = None
    mandate_id: str | None = None
    creditor_id: str | None = None
    end_to_end_ref: str | None = None


@dataclass
class ParsedStatement:
    iban: str | None = None
    account_name: str | None = None
    bank: str | None = None
    transactions: list[ParsedTransaction] = field(default_factory=list)


def decode(raw: bytes) -> str:
    """Depending on the version, ING exports UTF-8 (with BOM) or Windows-1252."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def parse_amount(value: str) -> Decimal:
    cleaned = value.strip().replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise IngCsvError(f"Ungültiger Betrag: {value!r}") from exc


def parse_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except ValueError as exc:
        raise IngCsvError(f"Ungültiges Datum: {value!r}") from exc


def normalize_iban(value: str) -> str:
    return value.replace(" ", "").upper()


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
        raise IngCsvError("Spalten fehlen: " + ", ".join(sorted(missing)))
    return mapping


def fingerprint(t: ParsedTransaction, occurrence: int) -> str:
    """Fingerprint of a transaction.

    The balance is deliberately left out so the same transaction is recognized
    as a duplicate in a later export covering a different period. Identical
    transactions on the same day (e.g. two times 2.50 € at the bakery) are told
    apart by the `occurrence` counter.
    """
    parts = [
        t.booking_date.isoformat(),
        f"{t.amount:.2f}",
        t.currency,
        " ".join(t.payee.split()).lower(),
        " ".join(t.purpose.split()).lower(),
        str(occurrence),
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


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
        raise IngCsvError("Keine ING-Umsatzanzeige erkannt (Kopfzeile „Buchung;…“ fehlt).")

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
            raise IngCsvError(f"Zeile {line_no}: {exc}") from exc

    # Store chronologically, oldest transaction first
    if not ascending:
        statement.transactions.reverse()
    statement.transactions.sort(key=lambda t: t.booking_date)

    assign_fingerprints(statement.transactions)
    return statement


def assign_fingerprints(transactions: list[ParsedTransaction]) -> None:
    """Sets `dedup_hash` for a chronologically sorted list of transactions."""
    seen: Counter[str] = Counter()
    for t in transactions:
        base = fingerprint(t, 0)
        t.dedup_hash = fingerprint(t, seen[base])
        seen[base] += 1
