from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from ..budget_month import get_settings, recompute
from ..deps import DB, CurrentUser
from ..models import Account, Category, Transaction
from ..schemas import BudgetSettingsIn, BudgetSettingsOut

router = APIRouter(prefix="/budget-month", tags=["budget-month"])


def _out(db: DB, household_id: int) -> BudgetSettingsOut:
    settings = get_settings(db, household_id)
    shifted = db.scalar(
        select(func.count(Transaction.id))
        .join(Account, Account.id == Transaction.account_id)
        .where(Account.household_id == household_id, Transaction.budget_date != Transaction.booking_date)
    )
    out = BudgetSettingsOut.model_validate(settings)
    out.shifted_count = shifted or 0
    return out


@router.get("/settings", response_model=BudgetSettingsOut)
def read_settings(db: DB, user: CurrentUser):
    out = _out(db, user.household_id)
    db.commit()
    return out


@router.put("/settings", response_model=BudgetSettingsOut)
def update_settings(data: BudgetSettingsIn, db: DB, user: CurrentUser):
    """Saves the settings and reassigns the budget month of all household transactions."""
    ids = set(data.salary_category_ids)
    if ids:
        known = set(
            db.scalars(select(Category.id).where(Category.household_id == user.household_id, Category.id.in_(ids)))
        )
        if known != ids:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekannte Kategorie")
    settings = get_settings(db, user.household_id)
    settings.salary_shift_enabled = data.salary_shift_enabled
    settings.salary_shift_days = data.salary_shift_days
    settings.salary_category_ids = sorted(ids)
    payees: list[str] = []
    for p in data.salary_payees:
        p = " ".join(p.split())[:255]
        if p and p.casefold() not in (x.casefold() for x in payees):
            payees.append(p)
    settings.salary_payees = payees
    settings.salary_auto_detect = data.salary_auto_detect
    recompute(db, user.household_id)
    db.commit()
    return _out(db, user.household_id)
