"""Directory of German banks and their FinTS PIN/TAN server addresses.

Budgie ships a compact directory in `banks.json`, generated from the public
domain (CC0) dataset `fints-institute-db` with known address changes applied
(see `scripts/build_bank_directory.py`). That dataset is a few years old, so a
server address can be outdated; the address of a bank connection can always be
edited.

Registered FinTS products receive the official institute list
(`fints_institute.csv`) from the Deutsche Kreditwirtschaft. If
`BUDGIE_FINTS_INSTITUTES_FILE` points to that file, it is used instead of the
bundled directory.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import unicodedata
from dataclasses import asdict, dataclass
from functools import lru_cache
from pathlib import Path

from ..config import get_settings

log = logging.getLogger(__name__)

BUNDLED = Path(__file__).with_name("banks.json")

ING_BANK_CODE = "50010517"
ING_FINTS_URL = "https://fints.ing.de/fints/"

# Server addresses that moved since the source data was collected. Applied to
# the bundled directory and to an official list alike.
URL_REPLACEMENTS = {
    # Fiducia & GAD merged into Atruvia (cooperative banks: Volksbanken, Raiffeisenbanken, Sparda, PSD …)
    "https://hbci11.fiducia.de/cgi-bin/hbciservlet": "https://fints1.atruvia.de/cgi-bin/hbciservlet",
    "https://hbci-pintan.gad.de/cgi-bin/hbciservlet": "https://fints2.atruvia.de/cgi-bin/hbciservlet",
    # Address Budgie has always used for ING
    "https://fints.ing-diba.de/fints/": ING_FINTS_URL,
}


@dataclass(frozen=True)
class Bank:
    bank_code: str
    name: str
    location: str
    bic: str
    server_url: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _fold(text: str) -> str:
    """Lowercase without accents, so "Muenchen", "München" and "munchen" match."""
    text = text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def _fix_url(url: str | None) -> str | None:
    url = (url or "").strip()
    if not url:
        return None
    if not url.startswith("http"):
        url = "https://" + url
    return URL_REPLACEMENTS.get(url, url)


def parse_institute_csv(raw: bytes) -> list[Bank]:
    """Reads the official FinTS institute list of the Deutsche Kreditwirtschaft.

    The file is semicolon separated and Windows-1252 encoded. Columns are found
    by their header, since their order changed between releases.
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    if not rows:
        return []
    header = [_fold(h).replace(" ", "") for h in rows[0]]

    def col(*needles: str) -> int | None:
        for i, h in enumerate(header):
            if all(n in h for n in needles):
                return i
        return None

    i_blz, i_bic, i_name, i_loc = col("blz"), col("bic"), col("institut"), col("ort")
    i_url = col("pin/tan", "url")
    if i_blz is None or i_name is None or i_url is None:
        raise ValueError("Unbekanntes Format der FinTS-Institutsliste")

    def get(row: list[str], i: int | None) -> str:
        return row[i].strip() if i is not None and i < len(row) else ""

    return [
        Bank(
            bank_code=get(row, i_blz),
            name=get(row, i_name),
            location=get(row, i_loc),
            bic=get(row, i_bic),
            server_url=_fix_url(get(row, i_url)),
        )
        for row in rows[1:]
        if len(get(row, i_blz)) == 8 and get(row, i_blz).isdigit()
    ]


def _dedupe(banks: list[Bank]) -> dict[str, Bank]:
    """One entry per bank code; the first entry with a server address wins."""
    result: dict[str, Bank] = {}
    for bank in banks:
        known = result.get(bank.bank_code)
        if known is None or (known.server_url is None and bank.server_url):
            result[bank.bank_code] = bank
    return result


@lru_cache
def _directory() -> dict[str, Bank]:
    path = get_settings().fints_institutes_file
    if path:
        try:
            return _dedupe(parse_institute_csv(Path(path).read_bytes()))
        except (OSError, ValueError):
            log.exception("FinTS-Institutsliste %s nicht lesbar, nutze die mitgelieferte Liste", path)
    data = json.loads(BUNDLED.read_text(encoding="utf-8"))
    banks = [Bank(bank_code=b[0], name=b[1], location=b[2], bic=b[3], server_url=_fix_url(b[4])) for b in data["banks"]]
    return _dedupe(banks)


def reload() -> None:
    _directory.cache_clear()


def lookup(bank_code: str) -> Bank | None:
    return _directory().get(bank_code.strip())


def search(query: str, limit: int = 20) -> list[Bank]:
    """Finds banks by bank code (BLZ), BIC, name or location.

    All words of the query must match. Banks with a FinTS address and shorter
    names (the main institute rather than a subsidiary) come first.
    """
    words = _fold(query).split()
    if not words:
        return []
    compact = "".join(words)
    if compact.isdigit():
        return [b for code, b in sorted(_directory().items()) if code.startswith(compact)][:limit]
    hits = []
    for bank in _directory().values():
        haystack = _fold(f"{bank.name} {bank.location} {bank.bic} {bank.bank_code}")
        if all(w in haystack for w in words):
            name = _fold(bank.name)
            # 0: name starts with the query, 1: a word starts with it, 2: somewhere inside
            tokens = name.replace("-", " ").replace("(", " ").split()
            rank = 0 if name.startswith(words[0]) else 1 if any(t.startswith(words[0]) for t in tokens) else 2
            hits.append(((rank, bank.server_url is None, len(bank.name), bank.bank_code), bank))
    hits.sort(key=lambda h: h[0])
    return [b for _, b in hits[:limit]]
