import json
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, CurrentUser, get_visible_account, visible_accounts_query
from ..importers import bank_csv, ing_csv
from ..importers.common import CsvError, ParsedStatement
from ..importers.store import store_transactions
from ..models import Account, CsvProfile, ImportBatch, User
from ..schemas import CsvFormatOut, CsvMappingIn, CsvPreviewOut, CsvProfileOut, ImportOut

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("", response_model=list[ImportOut])
def list_imports(db: DB, user: CurrentUser):
    ids = visible_accounts_query(user).with_only_columns(Account.id)
    return db.scalars(
        select(ImportBatch).where(ImportBatch.account_id.in_(ids)).order_by(ImportBatch.id.desc()).limit(50)
    ).all()


async def _read(file: UploadFile) -> bytes:
    raw = await file.read(get_settings().max_upload_bytes + 1)
    if len(raw) > get_settings().max_upload_bytes:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Datei ist zu groß")
    return raw


def _target_account(db: DB, user: User, statement: ParsedStatement, account_id: int | None, bank: str):
    """The account to import into: chosen by the user, or found or created by the IBAN in the file."""
    if account_id is not None:
        account = get_visible_account(db, user, account_id)
        if statement.iban and account.iban and statement.iban != account.iban:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Die Datei gehört zu {statement.iban}, nicht zu {account.iban}",
            )
        if statement.iban and not account.iban:
            account.iban = statement.iban
        return account, False
    if not statement.iban:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Keine IBAN in der Datei, bitte Konto auswählen")
    account = db.scalar(
        select(Account).where(Account.household_id == user.household_id, Account.iban == statement.iban)
    )
    if account is not None:
        return get_visible_account(db, user, account.id), False
    account = Account(
        household_id=user.household_id,
        name=statement.account_name or f"{bank} {statement.iban[-4:]}",
        iban=statement.iban,
        bank=statement.bank or bank,
        members=[user],
    )
    db.add(account)
    db.flush()
    return account, True


def _store(db: DB, user: User, statement: ParsedStatement, account_id, filename, source, bank, format_name):
    account, created = _target_account(db, user, statement, account_id, bank)
    batch = store_transactions(
        db,
        household_id=user.household_id,
        user_id=user.id,
        account=account,
        parsed=statement.transactions,
        source=source,
        filename=filename,
    )
    db.commit()
    out = ImportOut.model_validate(batch)
    out.account_created = created
    out.format_name = format_name
    return out


def _saved_profile(db: DB, user: User, raw: bytes) -> tuple[CsvProfile, bank_csv.CustomMapping] | None:
    """A saved mapping whose header row matches the file."""
    profiles = db.scalars(select(CsvProfile).where(CsvProfile.household_id == user.household_id)).all()
    tables: dict[str, bank_csv.CsvTable] = {}
    for profile in profiles:
        mapping = bank_csv.CustomMapping(**profile.mapping)
        table = tables.get(mapping.delimiter) or tables.setdefault(
            mapping.delimiter, bank_csv.read_table(raw, mapping.delimiter)
        )
        if mapping.header_row < len(table.rows):
            if bank_csv.header_signature(table.rows[mapping.header_row], mapping.delimiter) == profile.signature:
                return profile, mapping
    return None


@router.get("/csv/formats", response_model=list[CsvFormatOut])
def csv_formats(user: CurrentUser):
    """Bank export layouts Budgie recognizes on its own."""
    return [{"id": f.id, "name": f.name, "hint": f.hint} for f in bank_csv.FORMATS]


@router.post("/csv/preview", response_model=CsvPreviewOut)
async def csv_preview(db: DB, user: CurrentUser, file: Annotated[UploadFile, File()]):
    """Shows how Budgie reads a file: recognized layout, columns and a few rows."""
    raw = await _read(file)
    data = bank_csv.preview(raw)
    found = bank_csv.detect(raw)
    saved = None if found else _saved_profile(db, user, raw)
    data["format_name"] = found[0].name if found else saved[0].name if saved else None
    return data


@router.post("/csv", response_model=ImportOut, status_code=201)
async def import_csv(
    db: DB,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    account_id: Annotated[int | None, Form()] = None,
    mapping: Annotated[str | None, Form(description="CsvMappingIn as JSON, for unknown layouts")] = None,
    save_as: Annotated[str | None, Form(max_length=100)] = None,
):
    """Imports a CSV export of a bank.

    The layout is recognized from the header row (built-in bank layouts first,
    then mappings saved in this household). For an unknown layout the answer is
    422 with `detail.code == "unknown_format"`; the client then shows a preview
    (`POST /imports/csv/preview`) and sends the file again with a `mapping`.
    With `save_as`, the mapping is saved for files with the same header row.
    """
    raw = await _read(file)
    try:
        if mapping:
            try:
                chosen = CsvMappingIn.model_validate(json.loads(mapping))
            except (ValueError, ValidationError):
                raise CsvError("Ungültige Spaltenzuordnung") from None
            custom = bank_csv.CustomMapping(**chosen.model_dump())
            statement = bank_csv.parse_custom(raw, custom)
            name = (save_as or "").strip() or None
            if name:
                table = bank_csv.read_table(raw, custom.delimiter)
                signature = bank_csv.header_signature(table.rows[custom.header_row], custom.delimiter)
                profile = db.scalar(
                    select(CsvProfile).where(CsvProfile.household_id == user.household_id, CsvProfile.signature == signature)
                )
                if profile is None:
                    profile = CsvProfile(household_id=user.household_id, signature=signature)
                    db.add(profile)
                profile.name = name
                profile.mapping = chosen.model_dump()
            return _store(db, user, statement, account_id, file.filename, "csv", name or "Bank", name)

        found = bank_csv.detect(raw)
        if found is not None:
            fmt, table, header_row = found
            statement = bank_csv.parse(raw, fmt, table, header_row)
            return _store(db, user, statement, account_id, file.filename, fmt.source, fmt.bank, fmt.name)

        saved = _saved_profile(db, user, raw)
        if saved is not None:
            profile, custom = saved
            statement = bank_csv.parse_custom(raw, custom)
            return _store(db, user, statement, account_id, file.filename, "csv", profile.name, profile.name)
    except CsvError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        {
            "code": "unknown_format",
            "message": "Dieses CSV-Format kennt Budgie noch nicht. Bitte die Spalten zuordnen.",
        },
    )


@router.get("/csv/profiles", response_model=list[CsvProfileOut])
def list_csv_profiles(db: DB, user: CurrentUser):
    return db.scalars(
        select(CsvProfile).where(CsvProfile.household_id == user.household_id).order_by(CsvProfile.name)
    ).all()


@router.delete("/csv/profiles/{profile_id}", status_code=204)
def delete_csv_profile(profile_id: int, db: DB, user: CurrentUser):
    profile = db.get(CsvProfile, profile_id)
    if profile is None or profile.household_id != user.household_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vorlage nicht gefunden")
    db.delete(profile)
    db.commit()


@router.post("/ing-csv", response_model=ImportOut, status_code=201)
async def import_ing_csv(
    db: DB,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    account_id: Annotated[int | None, Form()] = None,
):
    """Imports an ING "Umsatzanzeige" (CSV). Kept for existing clients; `POST /imports/csv` handles all banks.

    Without `account_id`, the account is looked up by the IBAN in the file and
    created if needed. Transactions that were already imported are skipped.
    """
    raw = await _read(file)
    try:
        statement = ing_csv.parse(raw)
    except ing_csv.IngCsvError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None
    return _store(db, user, statement, account_id, file.filename, "ing_csv", "ING", "ING")
