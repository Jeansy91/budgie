"""Translations for messages the API shows to users (German and English).

The UI sends its language in the Accept-Language header. `LocaleMiddleware`
stores it for the duration of the request, and `t()` looks up messages in
that language. Code running outside a request (e.g. the FinTS sync thread)
sets the language explicitly with `use_locale()`.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import HTTPException
from starlette.types import ASGIApp, Receive, Scope, Send

LOCALES = ("de", "en")
DEFAULT_LOCALE = "de"

_locale: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)

MESSAGES: dict[str, dict[str, str]] = {
    # Authentication and users
    "auth.not_signed_in": {"de": "Nicht angemeldet", "en": "Not signed in"},
    "auth.session_expired": {"de": "Sitzung abgelaufen", "en": "Session expired"},
    "auth.admin_only": {"de": "Nur für Administratoren", "en": "Administrators only"},
    "auth.already_set_up": {"de": "Budgie ist bereits eingerichtet", "en": "Budgie is already set up"},
    "auth.invalid_login": {"de": "Nutzername oder Passwort falsch", "en": "Wrong username or password"},
    "auth.wrong_password": {"de": "Aktuelles Passwort falsch", "en": "Current password is wrong"},
    "users.username_taken": {"de": "Nutzername ist vergeben", "en": "Username is already taken"},
    "users.not_found": {"de": "Nutzer nicht gefunden", "en": "User not found"},
    "users.cannot_delete_self": {"de": "Du kannst dich nicht selbst löschen", "en": "You cannot delete yourself"},
    # Accounts
    "accounts.not_found": {"de": "Konto nicht gefunden", "en": "Account not found"},
    "accounts.unknown_user": {"de": "Unbekannter Nutzer", "en": "Unknown user"},
    "accounts.iban_exists": {"de": "Ein Konto mit dieser IBAN gibt es schon", "en": "An account with this IBAN already exists"},
    "accounts.default_name": {"de": "Konto {suffix}", "en": "Account {suffix}"},
    # Categories
    "categories.not_found": {"de": "Kategorie nicht gefunden", "en": "Category not found"},
    "categories.two_levels": {
        "de": "Nur zwei Ebenen: Haupt- und Unterkategorie",
        "en": "Only two levels: main category and subcategory",
    },
    "categories.exists": {"de": "Diese Kategorie gibt es schon", "en": "This category already exists"},
    "categories.kind_on_main": {
        "de": "Die Art wird an der Hauptkategorie festgelegt",
        "en": "The kind is set on the main category",
    },
    "categories.unknown": {"de": "Unbekannte Kategorie", "en": "Unknown category"},
    "categories.none": {"de": "Ohne Kategorie", "en": "Uncategorized"},
    # Rules and transactions
    "rules.not_found": {"de": "Regel nicht gefunden", "en": "Rule not found"},
    "rules.invalid_regex": {"de": "Ungültiger regulärer Ausdruck: {error}", "en": "Invalid regular expression: {error}"},
    "transactions.not_found": {"de": "Buchung nicht gefunden", "en": "Transaction not found"},
    "transactions.bad_month": {"de": "Monat im Format JJJJ-MM angeben", "en": "Give the month as YYYY-MM"},
    "transactions.no_payee_for_rule": {
        "de": "Kein Empfänger für die Regel vorhanden",
        "en": "There is no payee to create a rule from",
    },
    # CSV import
    "import.too_large": {"de": "Datei ist zu groß", "en": "The file is too large"},
    "import.wrong_account": {
        "de": "Die Datei gehört zu {file_iban}, nicht zu {account_iban}",
        "en": "The file belongs to {file_iban}, not to {account_iban}",
    },
    "import.no_iban": {
        "de": "Keine IBAN in der Datei, bitte Konto auswählen",
        "en": "The file contains no IBAN, please choose an account",
    },
    "csv.invalid_amount": {"de": "Ungültiger Betrag: {value}", "en": "Invalid amount: {value}"},
    "csv.invalid_date": {"de": "Ungültiges Datum: {value}", "en": "Invalid date: {value}"},
    "csv.missing_columns": {"de": "Spalten fehlen: {columns}", "en": "Missing columns: {columns}"},
    "csv.not_ing": {
        "de": "Keine ING-Umsatzanzeige erkannt (Kopfzeile „Buchung;…“ fehlt).",
        "en": "Not an ING transaction export (header line “Buchung;…” is missing).",
    },
    "csv.line": {"de": "Zeile {line}: {error}", "en": "Line {line}: {error}"},
    # AI
    "ai.disabled": {
        "de": "Die KI-Kategorisierung ist ausgeschaltet (BUDGIE_AI_ENABLED)",
        "en": "AI categorization is switched off (BUDGIE_AI_ENABLED)",
    },
    "ai.model_missing": {
        "de": "Modell {model} fehlt, bitte mit „ollama pull {model}“ laden",
        "en": "Model {model} is missing, load it with “ollama pull {model}”",
    },
    "ai.ollama_unreachable": {"de": "Ollama nicht erreichbar: {error}", "en": "Cannot reach Ollama: {error}"},
    # FinTS
    "fints.not_configured": {
        "de": "FinTS ist nicht eingerichtet, es fehlt: {missing}",
        "en": "FinTS is not set up, missing: {missing}",
    },
    "fints.connection_not_found": {"de": "Bankverbindung nicht gefunden", "en": "Bank connection not found"},
    "fints.job_not_found": {"de": "Abruf nicht gefunden", "en": "Sync not found"},
    "fints.no_tan_expected": {"de": "Der Abruf wartet gerade auf keine TAN", "en": "The sync is not waiting for a TAN"},
    "fints.already_running": {
        "de": "Für diese Bankverbindung läuft schon ein Abruf",
        "en": "A sync is already running for this bank connection",
    },
    "fints.product_id_missing": {
        "de": "BUDGIE_FINTS_PRODUCT_ID ist nicht gesetzt",
        "en": "BUDGIE_FINTS_PRODUCT_ID is not set",
    },
    "fints.no_accounts": {"de": "Die Bank hat keine Konten gemeldet", "en": "The bank reported no accounts"},
    "fints.foreign_account": {"de": "Konto gehört einem anderen Nutzer", "en": "Account belongs to another user"},
    "fints.connecting": {"de": "Verbinde mit der Bank …", "en": "Connecting to the bank …"},
    "fints.fetching_accounts": {"de": "Konten werden abgerufen …", "en": "Fetching accounts …"},
    "fints.fetching_transactions": {
        "de": "Umsätze für {account} werden abgerufen …",
        "en": "Fetching transactions for {account} …",
    },
    "fints.approve_in_app": {
        "de": "Bitte den Zugriff in der Banking-App freigeben.",
        "en": "Please approve the access in your banking app.",
    },
    "fints.enter_tan": {"de": "Bitte die TAN eingeben.", "en": "Please enter the TAN."},
    "fints.checking_tan": {"de": "TAN wird geprüft …", "en": "Checking TAN …"},
    "fints.approved": {"de": "Freigabe erhalten …", "en": "Approval received …"},
    "fints.done": {"de": "Abruf abgeschlossen", "en": "Sync complete"},
    "fints.cancelled": {"de": "Abruf abgebrochen", "en": "Sync cancelled"},
    "fints.failed": {"de": "Abruf fehlgeschlagen", "en": "Sync failed"},
    "fints.no_tan": {
        "de": "Keine TAN eingegangen, der Abruf wurde abgebrochen",
        "en": "No TAN received, the sync was cancelled",
    },
    "fints.no_approval": {
        "de": "Keine Freigabe in der App erhalten, der Abruf wurde abgebrochen",
        "en": "No approval received in the app, the sync was cancelled",
    },
    "fints.pin_rejected": {
        "de": (
            "Die Bank hat die Anmeldung abgelehnt. Bitte Zugangsnummer und PIN prüfen. "
            "Achtung: Nach mehreren falschen PINs sperrt die Bank den Zugang."
        ),
        "en": (
            "The bank rejected the login. Please check the login number and PIN. "
            "Note: the bank locks the access after several wrong PINs."
        ),
    },
    "fints.temporarily_locked": {
        "de": "Der Zugang ist vorübergehend gesperrt. Bitte im Online-Banking entsperren.",
        "en": "The access is temporarily locked. Please unlock it in online banking.",
    },
    "fints.sca_required": {
        "de": "Die Bank verlangt eine starke Kundenauthentifizierung, die nicht abgeschlossen wurde.",
        "en": "The bank requires strong customer authentication, which was not completed.",
    },
    "fints.connection_error": {
        "de": "Keine Verbindung zum FinTS-Server der Bank: {error}",
        "en": "Cannot connect to the bank's FinTS server: {error}",
    },
    "fints.error": {"de": "Fehler beim Abruf: {error}", "en": "Sync error: {error}"},
    "fints.import_name": {"de": "FinTS ab {date}", "en": "FinTS from {date}"},
    # Encryption of stored credentials
    "crypto.key_missing": {
        "de": "BUDGIE_SECRET_KEY fehlt oder ist kürzer als 16 Zeichen",
        "en": "BUDGIE_SECRET_KEY is missing or shorter than 16 characters",
    },
    "crypto.cannot_decrypt": {
        "de": "Gespeicherte Bankdaten lassen sich nicht entschlüsseln (BUDGIE_SECRET_KEY geändert?)",
        "en": "Stored bank credentials cannot be decrypted (was BUDGIE_SECRET_KEY changed?)",
    },
}


def get_locale() -> str:
    return _locale.get()


@contextmanager
def use_locale(locale: str) -> Iterator[None]:
    token = _locale.set(locale if locale in LOCALES else DEFAULT_LOCALE)
    try:
        yield
    finally:
        _locale.reset(token)


def t(key: str, **params: object) -> str:
    """Message `key` in the current language, with `{name}` placeholders filled in."""
    entry = MESSAGES[key]
    text = entry.get(get_locale()) or entry[DEFAULT_LOCALE]
    return text.format(**params) if params else text


def http_error(status_code: int, key: str, **params: object) -> HTTPException:
    """HTTPException with a translated detail message."""
    return HTTPException(status_code, t(key, **params))


def date_text(value) -> str:
    """Short numeric date in the current language."""
    return value.strftime("%d.%m.%Y") if get_locale() == "de" else value.isoformat()


def parse_accept_language(header: str | None) -> str:
    """Best supported language from an Accept-Language header, German otherwise."""
    if not header:
        return DEFAULT_LOCALE
    choices: list[tuple[float, int, str]] = []
    for i, part in enumerate(header.split(",")):
        lang, _, params = part.strip().partition(";")
        quality = 1.0
        for param in params.split(";"):
            name, _, value = param.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        base = lang.strip().lower().split("-")[0]
        if base in LOCALES and quality > 0:
            choices.append((-quality, i, base))
    return min(choices)[2] if choices else DEFAULT_LOCALE


class LocaleMiddleware:
    """Sets the request language from the Accept-Language header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        header = next((v.decode("latin-1") for k, v in scope["headers"] if k == b"accept-language"), None)
        with use_locale(parse_accept_language(header)):
            await self.app(scope, receive, send)


def category_name(category) -> str:
    """Display name of a category: default categories in the request language, own names as entered."""
    from .seed import DEFAULT_NAMES  # avoid an import cycle (seed imports models)

    if category.default_key:
        names = DEFAULT_NAMES.get(category.default_key)
        if names:
            return names.get(get_locale(), category.name)
    return category.name
