from fastapi import APIRouter, status
from sqlalchemy import func, select

from ..deps import DB, CurrentUser, visible_accounts_query
from ..i18n import http_error
from ..importers.common import normalize_iban
from ..models import Account, CategorySource, Transaction
from ..schemas import ExtraAccountOut, TransferAccountOut, TransferSettingsIn, TransferSettingsOut
from ..transfers import get_settings, is_valid_iban, redetect

router = APIRouter(prefix="/transfers", tags=["transfers"])


def _out(db: DB, user: CurrentUser, changed: int = 0) -> TransferSettingsOut:
    settings = get_settings(db, user.household_id)
    accounts = db.scalars(visible_accounts_query(user).where(Account.iban.is_not(None)).order_by(Account.id))
    detected = db.scalar(
        select(func.count(Transaction.id))
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.household_id == user.household_id, Transaction.category_source == CategorySource.transfer)
    )
    return TransferSettingsOut(
        auto_detect=settings.auto_detect,
        extra_accounts=[ExtraAccountOut(**a) for a in settings.extra_accounts],
        account_ibans=[TransferAccountOut(name=a.name, iban=a.iban or "") for a in accounts],
        detected_count=detected or 0,
        changed=changed,
    )


@router.get("/settings", response_model=TransferSettingsOut)
def read_settings(db: DB, user: CurrentUser):
    out = _out(db, user)
    db.commit()
    return out


@router.put("/settings", response_model=TransferSettingsOut)
def update_settings(data: TransferSettingsIn, db: DB, user: CurrentUser):
    """Saves the settings and recomputes the detected transfers of the household."""
    # One entry per IBAN; if an IBAN is listed twice, the first name wins
    extra: dict[str, str] = {}
    for item in data.extra_accounts:
        name = " ".join(item.name.split())
        if not name:
            raise http_error(status.HTTP_400_BAD_REQUEST, "transfers.name_required")
        iban = normalize_iban(item.iban)
        if not is_valid_iban(iban):
            raise http_error(status.HTTP_400_BAD_REQUEST, "transfers.invalid_iban", iban=item.iban.strip())
        extra.setdefault(iban, name)
    settings = get_settings(db, user.household_id)
    settings.auto_detect = data.auto_detect
    settings.extra_accounts = [{"name": n, "iban": i} for i, n in extra.items()]
    changed = redetect(db, user.household_id)
    db.commit()
    return _out(db, user, changed)
