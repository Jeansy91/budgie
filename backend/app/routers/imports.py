from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from ..config import get_settings
from ..deps import DB, CurrentUser, get_visible_account, visible_accounts_query
from ..importers import ing_csv
from ..importers.store import store_transactions
from ..i18n import http_error, t
from ..models import Account, ImportBatch
from ..schemas import ImportOut

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("", response_model=list[ImportOut])
def list_imports(db: DB, user: CurrentUser):
    ids = visible_accounts_query(user).with_only_columns(Account.id)
    return db.scalars(
        select(ImportBatch).where(ImportBatch.account_id.in_(ids)).order_by(ImportBatch.id.desc()).limit(50)
    ).all()


@router.post("/ing-csv", response_model=ImportOut, status_code=201)
async def import_ing_csv(
    db: DB,
    user: CurrentUser,
    file: Annotated[UploadFile, File()],
    account_id: Annotated[int | None, Form()] = None,
):
    """Imports an ING "Umsatzanzeige" (CSV).

    Without `account_id`, the account is looked up by the IBAN in the file and
    created if needed. Transactions that were already imported are skipped.
    """
    raw = await file.read(get_settings().max_upload_bytes + 1)
    if len(raw) > get_settings().max_upload_bytes:
        raise http_error(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "import.too_large")
    try:
        statement = ing_csv.parse(raw)
    except ing_csv.IngCsvError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from None

    created = False
    if account_id is not None:
        account = get_visible_account(db, user, account_id)
        if statement.iban and account.iban and statement.iban != account.iban:
            raise http_error(
                status.HTTP_400_BAD_REQUEST, "import.wrong_account", file_iban=statement.iban, account_iban=account.iban
            )
        if statement.iban and not account.iban:
            account.iban = statement.iban
    else:
        if not statement.iban:
            raise http_error(status.HTTP_400_BAD_REQUEST, "import.no_iban")
        account = db.scalar(
            select(Account).where(Account.household_id == user.household_id, Account.iban == statement.iban)
        )
        if account is not None:
            account = get_visible_account(db, user, account.id)
        else:
            account = Account(
                household_id=user.household_id,
                name=statement.account_name or t("accounts.default_name", suffix=statement.iban[-4:]),
                iban=statement.iban,
                bank=statement.bank or "ING",
                members=[user],
            )
            db.add(account)
            db.flush()
            created = True

    batch = store_transactions(
        db,
        household_id=user.household_id,
        user_id=user.id,
        account=account,
        parsed=statement.transactions,
        source="ing_csv",
        filename=file.filename,
    )
    db.commit()

    out = ImportOut.model_validate(batch)
    out.account_created = created
    return out
