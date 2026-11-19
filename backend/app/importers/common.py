"""Data types and helpers shared by all import sources (CSV files and FinTS)."""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


class CsvError(ValueError):
    """A CSV file could not be read. The message is shown to the user."""


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
    """Bank exports are UTF-8 (often with BOM) or Windows-1252."""
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def normalize_iban(value: str) -> str:
    return value.replace(" ", "").upper()


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


def assign_fingerprints(transactions: list[ParsedTransaction]) -> None:
    """Sets `dedup_hash` for a chronologically sorted list of transactions."""
    seen: Counter[str] = Counter()
    for t in transactions:
        base = fingerprint(t, 0)
        t.dedup_hash = fingerprint(t, seen[base])
        seen[base] += 1
