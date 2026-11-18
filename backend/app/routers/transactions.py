from datetime import date

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from ..ai import service as ai
from ..deps import DB, CurrentUser, visible_account_ids
from ..models import BudgetShift, Category, CategorySource, Rule, RuleField, RuleMatch, Transaction, User
from ..rules import apply_rules
from ..schemas import RuleOut, TransactionOut, TransactionPage, TransactionPatch, TransactionPatchOut
from .categories import get_category
from .rules import household_transactions, rule_out

router = APIRouter(prefix="/transactions", tags=["transactions"])


def month_bounds(month: str) -> tuple[date, date]:
    try:
        year, mon = (int(x) for x in month.split("-"))
        start = date(year, mon, 1)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Monat im Format JJJJ-MM angeben") from None
    end = date(year + (mon == 12), mon % 12 + 1, 1)
    return start, end


def get_transaction(db: DB, user: User, transaction_id: int) -> Transaction:
    t = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id, Transaction.account_id.in_(visible_account_ids(user))
        )
    )
    if t is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Buchung nicht gefunden")
    return t


@router.get("", response_model=TransactionPage)
def list_transactions(
    db: DB,
    user: CurrentUser,
    account_id: int | None = None,
    month: str | None = Query(None, description="YYYY-MM"),
    category_id: int | None = Query(None, description="Main category or subcategory"),
    uncategorized: bool = False,
    ai_review: bool = Query(False, description="Only AI assignments and suggestions nobody has reviewed yet"),
    q: str | None = Query(None, description="Search in payee and purpose"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    query = select(Transaction).where(Transaction.account_id.in_(visible_account_ids(user)))
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if month:
        start, end = month_bounds(month)
        # Filter by budget month so the list matches the overview
        query = query.where(Transaction.budget_date >= start, Transaction.budget_date < end)
    if category_id is not None:
        children = select(Category.id).where(Category.parent_id == category_id)
        query = query.where(or_(Transaction.category_id == category_id, Transaction.category_id.in_(children)))
    if uncategorized:
        query = query.where(Transaction.category_id.is_(None))
    if ai_review:
        query = query.where(
            or_(
                Transaction.category_source.in_([CategorySource.model, CategorySource.llm]),
                Transaction.suggested_category_id.is_not(None),
            )
        )
    if q:
        like = f"%{q.strip()}%"
        query = query.where(or_(Transaction.payee.ilike(like), Transaction.purpose.ilike(like)))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        query.order_by(Transaction.booking_date.desc(), Transaction.id.desc()).limit(limit).offset(offset)
    ).all()
    return TransactionPage(items=items, total=total)


@router.patch("/{transaction_id}", response_model=TransactionPatchOut)
def update_transaction(transaction_id: int, data: TransactionPatch, db: DB, user: CurrentUser):
    t = get_transaction(db, user, transaction_id)
    fields = data.model_fields_set
    if data.note is not None:
        t.note = data.note
    if data.budget_shift is not None:
        t.budget_shift = None if data.budget_shift == "auto" else BudgetShift(data.budget_shift)
    rule_result: RuleOut | None = None
    other_changed = 0

    if "category_id" in fields:
        was_manual = t.category_source == CategorySource.manual
        household_id = user.household_id
        t.category_confidence = None
        t.suggested_category_id, t.suggestion_confidence = None, None
        if data.category_id is None:
            t.category_id, t.category_source, t.rule_id = None, None, None
            if was_manual:
                ai.after_commit(db, lambda: ai.schedule_retrain(household_id))
        else:
            category = get_category(db, user, data.category_id)
            t.category_id, t.category_source, t.rule_id = category.id, CategorySource.manual, None
            # Every correction or confirmation is a training example for the AI
            ai.after_commit(db, lambda: ai.schedule_retrain(household_id))

            if data.create_rule:
                pattern = (data.rule_pattern or t.payee).strip()
                if not pattern:
                    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Kein Empfänger für die Regel vorhanden")
                rule = Rule(
                    household_id=user.household_id,
                    category_id=category.id,
                    field=RuleField.payee,
                    match_type=RuleMatch.contains,
                    pattern=pattern,
                    created_by=user.id,
                )
                db.add(rule)
                db.flush()
                if data.apply_rule:
                    others = [x for x in household_transactions(db, user) if x.id != t.id]
                    other_changed = apply_rules(db, user.household_id, others)
                db.commit()
                rule_result = rule_out(db, rule)

    db.commit()
    db.refresh(t)
    return TransactionPatchOut(transaction=TransactionOut.model_validate(t), rule=rule_result, other_changed=other_changed)
