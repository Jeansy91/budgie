"""CSV exports of German banks.

Every bank exports transactions a little differently: column names, date and
number formats, where the own IBAN is, and whether pending transactions are
included. A `CsvFormat` describes one export layout by its column headers;
the file is recognized by its header row and parsed with the shared code below.

Files of other banks can be imported with a `CustomMapping`: the user picks
which column holds the date, amount and so on. Such a mapping can be saved per
household and is then recognized by the file's header row next time.

The built-in layouts were written from the banks' documented or commonly
reported export formats and are tested against made-up sample files, not
against real exports of every bank.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from ..i18n import t
from . import ing_csv
from .common import CsvError, ParsedStatement, ParsedTransaction, assign_fingerprints, decode, normalize_iban

# Fields a column can be mapped to
FIELDS = (
    "booking_date",
    "value_date",
    "payee",
    # Counterparty of incoming payments, when the bank uses separate columns (DKB)
    "payer",
    "booking_text",
    "purpose",
    "amount",
    # Separate debit/credit columns instead of a signed amount (Deutsche Bank)
    "debit",
    "credit",
    "currency",
    "balance",
    "counterparty_iban",
    "counterparty_bic",
    "mandate_id",
    "creditor_id",
    "end_to_end_ref",
    # Booking status; rows with a status listed in `skip_status` are left out
    "status",
    # IBAN and name of the exported account itself
    "own_iban",
    "account_name",
)

DATE_FORMATS = {
    "dd.mm.yyyy": "%d.%m.%Y",
    "dd.mm.yy": "%d.%m.%y",
    "yyyy-mm-dd": "%Y-%m-%d",
    "dd/mm/yyyy": "%d/%m/%Y",
    "mm/dd/yyyy": "%m/%d/%Y",
}

IBAN_RE = re.compile(r"\b([A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30})\b")


def norm(header: str) -> str:
    """Normalized column name: lowercase, umlauts spelled out, single spaces."""
    text = header.strip().strip('"').lower()
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    return " ".join(text.split())


@dataclass(frozen=True)
class CsvFormat:
    id: str
    name: str
    # Bank name for accounts created from the file
    bank: str
    # Normalized column names that must all appear in the header row
    required: tuple[str, ...]
    # field → candidate column names (normalized), first match wins
    columns: dict[str, tuple[str, ...]] = field(default_factory=dict)
    decimal: str = "comma"
    date_formats: tuple[str, ...] = ("%d.%m.%Y", "%d.%m.%y")
    # Status values (lowercase, substring match) of pending transactions
    skip_status: tuple[str, ...] = ()
    # Adjusts a parsed transaction, e.g. splits a combined text column
    postprocess: Callable[[ParsedTransaction], None] | None = None
    # Parser of its own instead of the column mapping (ING keeps its proven parser)
    parser: Callable[[bytes], ParsedStatement] | None = None
    # Shown in the UI: where to find the export in online banking
    hint: str = ""

    @property
    def source(self) -> str:
        return f"{self.id}_csv"


# --- comdirect: payee, IBAN and purpose share one text column ---------------

_COMDIRECT_PAYEE = re.compile(
    r"(?:Auftraggeber|Empfänger|Empfaenger|Zahlungspflichtiger):\s*(.*?)\s*(?=(?:Kto/IBAN|BLZ/BIC|Buchungstext):|$)"
)
_COMDIRECT_IBAN = re.compile(r"Kto/IBAN:\s*([A-Z]{2}\d{2}[A-Z0-9]+)")
_COMDIRECT_TEXT = re.compile(r"Buchungstext:\s*(.*?)\s*(?:Ref\.\s*\S+\s*)?$")


def _comdirect(t: ParsedTransaction) -> None:
    text = " ".join(t.purpose.split())
    if m := _COMDIRECT_PAYEE.search(text):
        t.payee = m.group(1)
    if m := _COMDIRECT_IBAN.search(text):
        t.counterparty_iban = m.group(1)
    if m := _COMDIRECT_TEXT.search(text):
        t.purpose = m.group(1)
    elif t.payee:
        t.purpose = ""


FORMATS: tuple[CsvFormat, ...] = (
    CsvFormat(
        id="ing",
        name="ING",
        bank="ING",
        required=("auftraggeber/empfaenger", "betrag"),
        parser=ing_csv.parse,
        hint="Konto öffnen → Umsätze → Zeitraum wählen → als CSV exportieren.",
    ),
    CsvFormat(
        # "CSV-CAMT-Format" and the older "CSV-MT940-Format" of the Sparkassen
        id="sparkasse",
        name="Sparkasse",
        bank="Sparkasse",
        required=("auftragskonto", "buchungstag", "beguenstigter/zahlungspflichtiger", "betrag"),
        columns={
            "own_iban": ("auftragskonto",),
            "booking_date": ("buchungstag",),
            "value_date": ("valutadatum",),
            "booking_text": ("buchungstext",),
            "purpose": ("verwendungszweck",),
            "creditor_id": ("glaeubiger id",),
            "mandate_id": ("mandatsreferenz",),
            "end_to_end_ref": ("kundenreferenz (end-to-end)",),
            "payee": ("beguenstigter/zahlungspflichtiger",),
            "counterparty_iban": ("kontonummer/iban", "kontonummer"),
            "counterparty_bic": ("bic (swift-code)",),
            "amount": ("betrag",),
            "currency": ("waehrung",),
            "status": ("info",),
        },
        skip_status=("vorgemerkt",),
        hint="Umsätze → Export → „CSV-CAMT-Format“.",
    ),
    CsvFormat(
        # Volksbanken, Raiffeisenbanken and other banks on the Atruvia platform
        id="vr",
        name="Volksbank / Raiffeisenbank",
        bank="Volksbank",
        required=("iban auftragskonto", "buchungstag", "name zahlungsbeteiligter", "betrag"),
        columns={
            "account_name": ("bezeichnung auftragskonto",),
            "own_iban": ("iban auftragskonto",),
            "booking_date": ("buchungstag",),
            "value_date": ("valutadatum",),
            "payee": ("name zahlungsbeteiligter",),
            "counterparty_iban": ("iban zahlungsbeteiligter",),
            "counterparty_bic": ("bic (swift-code) zahlungsbeteiligter",),
            "booking_text": ("buchungstext",),
            "purpose": ("verwendungszweck",),
            "amount": ("betrag",),
            "currency": ("waehrung",),
            "balance": ("saldo nach buchung",),
            "creditor_id": ("glaeubiger id",),
            "mandate_id": ("mandatsreferenz",),
        },
        hint="Umsätze → Export → CSV.",
    ),
    CsvFormat(
        # Current DKB banking (since 2023)
        id="dkb",
        name="DKB",
        bank="DKB",
        required=("buchungsdatum", "zahlungsempfaenger*in", "betrag (€)"),
        columns={
            "booking_date": ("buchungsdatum",),
            "value_date": ("wertstellung",),
            "status": ("status",),
            "payer": ("zahlungspflichtige*r",),
            "payee": ("zahlungsempfaenger*in",),
            "purpose": ("verwendungszweck",),
            "booking_text": ("umsatztyp",),
            "counterparty_iban": ("iban",),
            "amount": ("betrag (€)",),
            "creditor_id": ("glaeubiger-id",),
            "mandate_id": ("mandatsreferenz",),
            "end_to_end_ref": ("kundenreferenz",),
        },
        skip_status=("vorgemerkt",),
        hint="Konto → Umsätze → Download-Symbol → CSV.",
    ),
    CsvFormat(
        # DKB banking before 2023
        id="dkb_legacy",
        name="DKB (bis 2023)",
        bank="DKB",
        required=("buchungstag", "auftraggeber / beguenstigter", "betrag (eur)"),
        columns={
            "booking_date": ("buchungstag",),
            "value_date": ("wertstellung",),
            "booking_text": ("buchungstext",),
            "payee": ("auftraggeber / beguenstigter",),
            "purpose": ("verwendungszweck",),
            "counterparty_iban": ("kontonummer",),
            "amount": ("betrag (eur)",),
            "creditor_id": ("glaeubiger-id",),
            "mandate_id": ("mandatsreferenz",),
            "end_to_end_ref": ("kundenreferenz",),
        },
    ),
    CsvFormat(
        id="comdirect",
        name="comdirect",
        bank="comdirect",
        required=("buchungstag", "vorgang", "buchungstext", "umsatz in eur"),
        columns={
            "booking_date": ("buchungstag",),
            "value_date": ("wertstellung (valuta)",),
            "booking_text": ("vorgang",),
            "purpose": ("buchungstext",),
            "amount": ("umsatz in eur",),
        },
        postprocess=_comdirect,
        hint="Umsätze → Zeitraum wählen → Export als CSV. Nur das erste Konto der Datei wird importiert.",
    ),
    CsvFormat(
        id="commerzbank",
        name="Commerzbank",
        bank="Commerzbank",
        required=("buchungstag", "umsatzart", "buchungstext", "betrag"),
        columns={
            "booking_date": ("buchungstag",),
            "value_date": ("wertstellung",),
            "booking_text": ("umsatzart",),
            "purpose": ("buchungstext",),
            "amount": ("betrag",),
            "currency": ("waehrung",),
            "own_iban": ("iban auftraggeberkonto",),
        },
    ),
    CsvFormat(
        id="deutsche_bank",
        name="Deutsche Bank",
        bank="Deutsche Bank",
        required=("buchungstag", "beguenstigter / auftraggeber", "soll", "haben"),
        columns={
            "booking_date": ("buchungstag",),
            "value_date": ("wert",),
            "booking_text": ("umsatzart",),
            "payee": ("beguenstigter / auftraggeber",),
            "purpose": ("verwendungszweck",),
            "counterparty_iban": ("iban",),
            "counterparty_bic": ("bic",),
            "end_to_end_ref": ("kundenreferenz",),
            "mandate_id": ("mandatsreferenz",),
            "creditor_id": ("glaeubiger id",),
            "debit": ("soll",),
            "credit": ("haben",),
            "currency": ("waehrung",),
        },
    ),
    CsvFormat(
        id="n26",
        name="N26",
        bank="N26",
        required=("booking date", "partner name", "amount (eur)"),
        columns={
            "booking_date": ("booking date",),
            "value_date": ("value date",),
            "payee": ("partner name",),
            "counterparty_iban": ("partner iban",),
            "booking_text": ("type",),
            "purpose": ("payment reference",),
            "account_name": ("account name",),
            "amount": ("amount (eur)",),
        },
        decimal="point",
        date_formats=("%Y-%m-%d",),
        hint="Web-App → Umsätze → Download → CSV.",
    ),
    CsvFormat(
        # N26 exports before 2024
        id="n26_legacy",
        name="N26 (alt)",
        bank="N26",
        required=("datum", "empfaenger", "betrag (eur)"),
        columns={
            "booking_date": ("datum",),
            "payee": ("empfaenger",),
            "counterparty_iban": ("kontonummer",),
            "booking_text": ("transaktionstyp",),
            "purpose": ("verwendungszweck",),
            "amount": ("betrag (eur)",),
        },
        decimal="point",
        date_formats=("%Y-%m-%d",),
    ),
)

FORMATS_BY_ID = {f.id: f for f in FORMATS}


@dataclass
class CustomMapping:
    """Column assignment chosen by the user for an unknown file layout."""

    delimiter: str
    header_row: int
    # field → column index
    columns: dict[str, int]
    date_format: str = "dd.mm.yyyy"
    decimal: str = "comma"

    def validate(self) -> None:
        if self.delimiter not in (";", ",", "\t", "|"):
            raise CsvError(t("csv.invalid_delimiter"))
        if self.date_format not in DATE_FORMATS:
            raise CsvError(t("csv.unknown_date_format"))
        if self.decimal not in ("comma", "point"):
            raise CsvError(t("csv.unknown_number_format"))
        unknown = set(self.columns) - set(FIELDS)
        if unknown:
            raise CsvError(t("csv.unknown_fields", fields=", ".join(sorted(unknown))))
        if "booking_date" not in self.columns:
            raise CsvError(t("csv.need_date_column"))
        if "amount" not in self.columns and not {"debit", "credit"} & set(self.columns):
            raise CsvError(t("csv.need_amount_column"))


# --- Reading ----------------------------------------------------------------


@dataclass
class CsvTable:
    text: str
    delimiter: str
    rows: list[list[str]]


def read_table(raw: bytes, delimiter: str | None = None) -> CsvTable:
    text = decode(raw)
    delimiter = delimiter or sniff_delimiter(text)
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    return CsvTable(text=text, delimiter=delimiter, rows=rows)


def sniff_delimiter(text: str) -> str:
    """The delimiter that splits most lines into the same number of columns."""
    lines = [line for line in text.splitlines() if line.strip()][:200]
    best, best_score = ";", 0
    for candidate in (";", ",", "\t", "|"):
        counts: dict[int, int] = {}
        for row in csv.reader(lines, delimiter=candidate):
            if len(row) > 1:
                counts[len(row)] = counts.get(len(row), 0) + 1
        if counts:
            width, lines_with_width = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
            score = lines_with_width * width
            if score > best_score:
                best, best_score = candidate, score
    return best


def header_signature(header: list[str], delimiter: str) -> str:
    """Identifies a file layout by its header row, for saved mappings."""
    joined = "\x1f".join(norm(h) for h in header)
    return hashlib.sha256(f"{delimiter}\x1e{joined}".encode()).hexdigest()


def detect(raw: bytes) -> tuple[CsvFormat, CsvTable, int] | None:
    """Recognizes a built-in layout. Returns the format, table and header row index."""
    tables: dict[str, CsvTable] = {}
    for fmt in FORMATS:
        delimiter = "," if fmt.decimal == "point" else ";"
        table = tables.get(delimiter) or tables.setdefault(delimiter, read_table(raw, delimiter))
        for i, row in enumerate(table.rows[:60]):
            names = {norm(c) for c in row}
            if all(r in names for r in fmt.required):
                return fmt, table, i
    return None


def parse(raw: bytes, fmt: CsvFormat, table: CsvTable | None = None, header_row: int | None = None) -> ParsedStatement:
    """Parses a file in a known layout."""
    if fmt.parser is not None:
        statement = fmt.parser(raw)
        statement.bank = statement.bank or fmt.bank
        return statement
    if table is None or header_row is None:
        found = detect(raw)
        if found is None or found[0] is not fmt:
            raise CsvError(t("csv.wrong_format", name=fmt.name))
        _, table, header_row = found
    header = [norm(c) for c in table.rows[header_row]]
    columns: dict[str, int] = {}
    for name, candidates in fmt.columns.items():
        for candidate in candidates:
            if candidate in header:
                columns[name] = header.index(candidate)
                break
    statement = _parse_rows(
        table.rows,
        header_row,
        columns,
        date_formats=fmt.date_formats,
        decimal=fmt.decimal,
        skip_status=fmt.skip_status,
        postprocess=fmt.postprocess,
    )
    statement.bank = fmt.bank
    return statement


def parse_custom(raw: bytes, mapping: CustomMapping) -> ParsedStatement:
    mapping.validate()
    table = read_table(raw, mapping.delimiter)
    if not 0 <= mapping.header_row < len(table.rows):
        raise CsvError(t("csv.header_outside"))
    width = len(table.rows[mapping.header_row])
    if any(not 0 <= idx < max(width, 1) for idx in mapping.columns.values()):
        raise CsvError(t("csv.column_missing"))
    return _parse_rows(
        table.rows,
        mapping.header_row,
        dict(mapping.columns),
        date_formats=(DATE_FORMATS[mapping.date_format],),
        decimal=mapping.decimal,
    )


def parse_amount(value: str, decimal: str = "comma") -> Decimal:
    cleaned = value.strip().replace("\xa0", "").replace(" ", "").replace("€", "").replace("EUR", "")
    negative = cleaned.endswith("-")
    cleaned = cleaned.rstrip("-").lstrip("+")
    if decimal == "comma":
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        amount = Decimal(cleaned)
    except InvalidOperation as exc:
        raise CsvError(t("csv.invalid_amount", value=repr(value))) from exc
    return -amount if negative else amount


def parse_date(value: str, formats: tuple[str, ...]) -> date:
    for fmt in formats:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    raise CsvError(t("csv.invalid_date", value=repr(value)))


def _parse_rows(
    rows: list[list[str]],
    header_row: int,
    columns: dict[str, int],
    *,
    date_formats: tuple[str, ...],
    decimal: str,
    skip_status: tuple[str, ...] = (),
    postprocess: Callable[[ParsedTransaction], None] | None = None,
) -> ParsedStatement:
    statement = ParsedStatement()
    header = rows[header_row]

    def get(row: list[str], name: str) -> str:
        idx = columns.get(name)
        return row[idx].strip() if idx is not None and idx < len(row) else ""

    # The own IBAN often appears above the table ("Konto;Girokonto DE12 …")
    for row in rows[:header_row]:
        for cell in row:
            if m := IBAN_RE.search(cell.upper()):
                statement.iban = normalize_iban(m.group(1))
                break
        if statement.iban:
            break

    date_header = norm(header[columns["booking_date"]]) if columns.get("booking_date") is not None else ""
    for line_no, row in enumerate(rows[header_row + 1 :], start=header_row + 2):
        if not row or not any(cell.strip() for cell in row):
            continue
        raw_date = get(row, "booking_date")
        # A second account section with its own header ends the first table (comdirect)
        if norm(raw_date) == date_header:
            break
        # Pending transactions ("offen") and summary lines ("Kontostand") have no date
        if not any(ch.isdigit() for ch in raw_date):
            continue
        status = get(row, "status").lower()
        if status and any(s in status for s in skip_status):
            continue
        try:
            if "amount" in columns:
                amount = parse_amount(get(row, "amount"), decimal)
            else:
                debit, credit = get(row, "debit"), get(row, "credit")
                amount = (parse_amount(credit, decimal) if credit else Decimal(0)) - (
                    abs(parse_amount(debit, decimal)) if debit else Decimal(0)
                )
            value_date = get(row, "value_date")
            balance = get(row, "balance")
            payee = get(row, "payee")
            if amount > 0 and get(row, "payer"):
                payee = get(row, "payer")
            tx = ParsedTransaction(
                booking_date=parse_date(raw_date, date_formats),
                value_date=parse_date(value_date, date_formats) if value_date else None,
                payee=payee,
                booking_text=get(row, "booking_text"),
                # N26 writes "-" for an empty reference
                purpose="" if get(row, "purpose") == "-" else get(row, "purpose"),
                amount=amount,
                currency=get(row, "currency") or "EUR",
                balance_after=parse_amount(balance, decimal) if balance else None,
                counterparty_iban=normalize_iban(get(row, "counterparty_iban")) or None,
                counterparty_bic=get(row, "counterparty_bic") or None,
                mandate_id=get(row, "mandate_id") or None,
                creditor_id=get(row, "creditor_id") or None,
                end_to_end_ref=_reference(get(row, "end_to_end_ref")),
            )
        except CsvError as exc:
            raise CsvError(t("csv.line", line=line_no, error=exc)) from exc
        if postprocess is not None:
            postprocess(tx)
        if tx.counterparty_iban and not IBAN_RE.fullmatch(tx.counterparty_iban):
            # Old account numbers (Kontonummer) are not IBANs
            tx.counterparty_iban = None
        if not statement.iban and (own := normalize_iban(get(row, "own_iban"))) and IBAN_RE.fullmatch(own):
            statement.iban = own
        if not statement.account_name and get(row, "account_name"):
            statement.account_name = get(row, "account_name")
        statement.transactions.append(tx)

    if not statement.transactions and header_row + 1 >= len(rows):
        raise CsvError(t("csv.no_transactions"))
    # Most banks export the newest transaction first; store oldest first, keeping
    # the order within a day stable so fingerprints match across exports.
    txs = statement.transactions
    if len(txs) > 1 and txs[0].booking_date > txs[-1].booking_date:
        txs.reverse()
    txs.sort(key=lambda t: t.booking_date)
    assign_fingerprints(txs)
    return statement


def _reference(value: str) -> str | None:
    return None if not value or value.upper() == "NOTPROVIDED" else value


# --- Preview for the column mapping -----------------------------------------


def _looks_like_date(value: str) -> str | None:
    value = value.strip()
    for key, fmt in DATE_FORMATS.items():
        try:
            datetime.strptime(value, fmt)
            return key
        except ValueError:
            continue
    return None


_AMOUNT_RE = re.compile(r"^[+-]?[\d.,\s]+-?(?:\s?(?:€|EUR))?$")

# Column names (normalized, substring match) that suggest a field
_SUGGEST = (
    ("booking_date", ("buchungstag", "buchungsdatum", "buchung", "booking date", "datum", "date")),
    ("value_date", ("valuta", "wertstellung", "value date", "wert")),
    ("payee", ("empfaenger", "auftraggeber", "zahlungsbeteiligter", "beguenstigter", "partner", "payee", "name")),
    ("purpose", ("verwendungszweck", "zweck", "payment reference", "reference", "beschreibung", "description")),
    ("booking_text", ("buchungstext", "umsatzart", "vorgang", "transaktionstyp", "type")),
    ("counterparty_iban", ("iban",)),
    ("balance", ("saldo", "kontostand", "balance")),
    ("currency", ("waehrung", "currency")),
    ("debit", ("soll", "ausgang", "debit")),
    ("credit", ("haben", "eingang", "credit")),
    ("amount", ("betrag", "umsatz", "amount")),
)


def preview(raw: bytes, sample_rows: int = 5) -> dict:
    """Guesses delimiter, header row and column assignment of an unknown file."""
    table = read_table(raw)
    rows = table.rows
    header_row = 0
    for i, row in enumerate(rows[:60]):
        if sum(1 for c in row if c.strip()) < 3 or any(_looks_like_date(c) for c in row):
            continue
        following = next((r for r in rows[i + 1 :] if any(c.strip() for c in r)), None)
        if following and len(following) >= len(row) - 1 and any(_looks_like_date(c) for c in following):
            header_row = i
            break
    header = rows[header_row] if rows else []
    sample = [r for r in rows[header_row + 1 :] if any(c.strip() for c in r)][:sample_rows]

    columns: dict[str, int] = {}
    used: set[int] = set()
    for name, needles in _SUGGEST:
        for idx, col in enumerate(header):
            if idx not in used and any(n in norm(col) for n in needles):
                columns[name] = idx
                used.add(idx)
                break
    if "amount" in columns and ("debit" in columns or "credit" in columns):
        columns.pop("debit", None)
        columns.pop("credit", None)

    date_format = "dd.mm.yyyy"
    if "booking_date" in columns:
        for r in sample:
            if columns["booking_date"] < len(r) and (key := _looks_like_date(r[columns["booking_date"]])):
                date_format = key
                break
    decimal = "comma"
    amount_idx = columns.get("amount", columns.get("debit"))
    if amount_idx is not None:
        values = [r[amount_idx].strip() for r in sample if amount_idx < len(r) and r[amount_idx].strip()]
        if values and all(re.search(r"\.\d{2}$", v.rstrip("-€ EUR")) for v in values):
            decimal = "point"

    return {
        "delimiter": table.delimiter,
        "header_row": header_row,
        "columns": header,
        "rows": sample,
        "suggestion": {"columns": columns, "date_format": date_format, "decimal": decimal},
    }
