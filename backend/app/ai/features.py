"""Turn a transaction into the text the classifier sees."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

# Mandate references, card numbers, dates etc. carry no meaning
_WITH_DIGITS = re.compile(r"\S*\d\S*")
_NON_WORD = re.compile(r"[^\w&+]+")


@dataclass(frozen=True)
class TxText:
    payee: str
    booking_text: str
    purpose: str
    amount: Decimal | float
    booking_date: date | None = None


_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def clean(text: str) -> str:
    # Banks sometimes spell out umlauts and sometimes don't: treat "Bäckerei" and "Baeckerei" the same
    text = _WITH_DIGITS.sub(" ", (text or "").casefold().translate(_UMLAUTS))
    return " ".join(_NON_WORD.sub(" ", text).split())


def text_feature(t: TxText) -> str:
    """Free text for the character n-grams. The payee counts twice."""
    payee = clean(t.payee)
    return f"{payee} | {payee} | {clean(t.booking_text)} | {clean(t.purpose)[:300]}"


def meta_feature(t: TxText) -> str:
    """Structural features as pseudo-words: direction, amount size, booking type, third of month."""
    amount = float(t.amount)
    tokens = ["dir_in" if amount > 0 else "dir_out"]
    size = abs(amount)
    bucket = 0 if size < 1 else min(int(math.log10(size) * 3), 12)
    tokens.append(f"amt_{bucket}")
    tokens.append(f"{tokens[0]}_amt_{bucket}")
    if size >= 10 and size == round(size):
        tokens.append("amt_round")
    for word in clean(t.booking_text).split()[:3]:
        tokens.append(f"bt_{word}")
    if t.booking_date is not None:
        day = t.booking_date.day
        tokens.append("dom_early" if day <= 5 else "dom_late" if day >= 25 else "dom_mid")
    return " ".join(tokens)
