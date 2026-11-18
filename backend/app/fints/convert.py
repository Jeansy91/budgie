"""Converts transactions from python-fints into the importer format.

Depending on the bank, python-fints returns MT940 (`mt940.models.Transaction`)
or camt.052 (`fints.models.Transaction`). Both have a `data` dict with largely
the same keys, e.g. `date` (value date), `entry_date` (booking date),
`amount`, `applicant_name`, `purpose` and `posting_text`.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from ..importers.ing_csv import ParsedTransaction, assign_fingerprints


def _text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = " ".join(str(v) for v in value if v)
    return " ".join(str(value).split())


def _date(value) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return date(value.year, value.month, value.day)
    return None


def to_parsed(transactions) -> list[ParsedTransaction]:
    result: list[ParsedTransaction] = []
    for t in transactions:
        d = t.data
        booking = _date(d.get("entry_date")) or _date(d.get("guessed_entry_date")) or _date(d.get("date"))
        if booking is None:
            continue
        amount_obj = d.get("amount")
        amount = Decimal(str(getattr(amount_obj, "amount", amount_obj))).quantize(Decimal("0.01"))
        currency = getattr(amount_obj, "currency", None) or d.get("currency") or "EUR"
        result.append(
            ParsedTransaction(
                booking_date=booking,
                value_date=_date(d.get("date")),
                payee=_text(d.get("applicant_name")),
                booking_text=_text(d.get("posting_text")),
                purpose=_text(d.get("purpose")),
                amount=amount,
                currency=currency,
                balance_after=None,
            )
        )
    result.sort(key=lambda p: p.booking_date)
    assign_fingerprints(result)
    return result
