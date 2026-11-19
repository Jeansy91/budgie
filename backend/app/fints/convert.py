"""Converts transactions from python-fints into the importer format.

Depending on the bank, python-fints returns MT940 (`mt940.models.Transaction`)
or camt.052 (`fints.models.Transaction`). Both have a `data` dict with largely
the same keys, e.g. `date` (value date), `entry_date` (booking date),
`amount`, `applicant_name`, `purpose` and `posting_text`.

SEPA details of the counterparty (IBAN, BIC, mandate reference, creditor ID,
end-to-end reference) are taken over as well when the bank delivers them.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from ..importers.common import ParsedTransaction, assign_fingerprints


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


# IBAN lengths of the SEPA countries most likely to appear on a German account
IBAN_LENGTHS = {
    "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
    "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26,
    "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15,
    "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
}
_IBAN_START = re.compile(r"([A-Z]{2})(\d{2})")
# Placeholders banks send instead of a real reference
_EMPTY_REFS = {"", "NOTPROVIDED", "NONREF", "NONE"}


def _ref(value) -> str | None:
    text = _text(value)
    return None if text.upper() in _EMPTY_REFS else text


def _iban(value) -> str | None:
    text = _text(value).replace(" ", "").upper()
    return text if _looks_like_iban(text) else None


def _looks_like_iban(text: str) -> bool:
    m = _IBAN_START.match(text)
    return bool(m) and IBAN_LENGTHS.get(m.group(1)) == len(text) and text.isalnum()


def split_iban_name(name: str) -> tuple[str | None, str]:
    """Splits an IBAN glued to the front of the counterparty name.

    With MT940, the counterparty account (subfield ?31) and the name (?32/?33)
    end up concatenated in `applicant_name`, e.g.
    "DE89370400440532013000Stadtwerke Musterstadt".
    """
    m = _IBAN_START.match(name)
    length = IBAN_LENGTHS.get(m.group(1)) if m else None
    if length and len(name) >= length and name[:length].isalnum():
        return name[:length], name[length:].strip()
    return None, name


def _camt_value(d: dict, *suffixes: str) -> str | None:
    """camt.052: first value whose (translated) key ends with one of the suffixes."""
    for key, value in d.items():
        if isinstance(key, str) and value and key.endswith(suffixes):
            return value
    return None


def _sepa_details(d: dict, payee: str) -> tuple[dict, str]:
    credit = d.get("status") == "C"
    iban = _iban(d.get("applicant_iban")) or _iban(d.get("gvc_applicant_iban"))
    if iban is None:
        iban, payee = split_iban_name(payee)
    elif payee.startswith(iban):
        payee = payee[len(iban) :].strip()
    agent = "DebtorAgent" if credit else "CreditorAgent"
    bic = (
        d.get("applicant_bin")
        or d.get("gvc_applicant_bin")
        or _camt_value(d, f"{agent}.FinancialInstitutionIdentification.BIC", f"{agent}.FinancialInstitutionIdentification.BICFI")
    )
    details = {
        "counterparty_iban": iban,
        "counterparty_bic": _ref(bic),
        "mandate_id": _ref(d.get("additional_position_reference") or _camt_value(d, "MandateIdentification")),
        "creditor_id": _ref(d.get("applicant_creditor_id")),
        "end_to_end_ref": _ref(d.get("end_to_end_reference")),
    }
    return details, payee


def to_parsed(transactions) -> list[ParsedTransaction]:
    result: list[ParsedTransaction] = []
    details: dict[int, tuple[dict, str]] = {}
    for t in transactions:
        d = t.data
        booking = _date(d.get("entry_date")) or _date(d.get("guessed_entry_date")) or _date(d.get("date"))
        if booking is None:
            continue
        amount_obj = d.get("amount")
        amount = Decimal(str(getattr(amount_obj, "amount", amount_obj))).quantize(Decimal("0.01"))
        currency = getattr(amount_obj, "currency", None) or d.get("currency") or "EUR"
        payee = _text(d.get("applicant_name"))
        p = ParsedTransaction(
            booking_date=booking,
            value_date=_date(d.get("date")),
            payee=payee,
            booking_text=_text(d.get("posting_text")),
            purpose=_text(d.get("purpose")),
            amount=amount,
            currency=currency,
            balance_after=None,
        )
        details[id(p)] = _sepa_details(d, payee)
        result.append(p)
    result.sort(key=lambda p: p.booking_date)
    # Fingerprints use the payee exactly as delivered, so transactions imported
    # before the IBAN was split off are still recognized as duplicates.
    assign_fingerprints(result)
    for p in result:
        sepa, p.payee = details[id(p)]
        for key, value in sepa.items():
            setattr(p, key, value)
    return result
