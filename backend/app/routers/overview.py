from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Query
from sqlalchemy import func, literal_column, select
from sqlalchemy.orm import aliased

from ..deps import DB, CurrentUser, visible_account_ids
from ..i18n import category_name, t
from ..models import Category, CategoryKind, Transaction
from ..schemas import CategorySum, MonthTotal, OverviewOut
from .transactions import month_bounds

router = APIRouter(prefix="/overview", tags=["overview"])

ZERO = Decimal("0.00")


@router.get("", response_model=OverviewOut)
def overview(
    db: DB,
    user: CurrentUser,
    month: str | None = Query(None, description="YYYY-MM, default: current month"),
    account_id: int | None = None,
    history_months: int = Query(12, ge=1, le=36),
):
    """Monthly overview: income, expenses, totals per category and history.

    Totals are based on the budget month (`budget_date`): a salary paid at the
    end of a month counts towards the following month, see app/budget_month.py.
    Transfers between own accounts count as neither income nor expense.
    Uncategorized transactions count by their sign.
    """
    month = month or date.today().strftime("%Y-%m")
    start, end = month_bounds(month)

    base = [Transaction.account_id.in_(visible_account_ids(user))]
    if account_id is not None:
        base.append(Transaction.account_id == account_id)

    rows = db.execute(
        select(Transaction.category_id, func.sum(Transaction.amount), func.count(Transaction.id))
        .where(*base, Transaction.budget_date >= start, Transaction.budget_date < end)
        .group_by(Transaction.category_id)
    ).all()

    categories = {
        c.id: c for c in db.scalars(select(Category).where(Category.household_id == user.household_id))
    }

    income = expenses = transfers = ZERO
    uncategorized_count = 0
    groups: dict[CategoryKind, dict[int | None, CategorySum]] = {CategoryKind.expense: {}, CategoryKind.income: {}}

    def add(kind: CategoryKind, main_id: int | None, main_name: str, sub: Category | None, amount, count):
        bucket = groups[kind].setdefault(
            main_id, CategorySum(category_id=main_id, name=main_name, amount=ZERO, count=0)
        )
        bucket.amount += amount
        bucket.count += count
        if sub is not None:
            child = next((c for c in bucket.children if c.category_id == sub.id), None)
            if child is None:
                child = CategorySum(category_id=sub.id, name=category_name(sub), amount=ZERO, count=0)
                bucket.children.append(child)
            child.amount += amount
            child.count += count

    for category_id, amount, count in rows:
        amount = Decimal(amount)
        category = categories.get(category_id)
        if category is None:
            uncategorized_count += count
            kind = CategoryKind.income if amount > 0 else CategoryKind.expense
            add(kind, None, t("categories.none"), None, amount, count)
        else:
            main = categories[category.parent_id] if category.parent_id else category
            kind = main.kind
            if kind == CategoryKind.transfer:
                transfers += amount
                continue
            add(kind, main.id, category_name(main), category if category.parent_id else None, amount, count)
        if kind == CategoryKind.income:
            income += amount
        else:
            expenses += amount

    # Income moved here from the previous month
    income_from_previous_month = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount), 0)).where(
            *base,
            Transaction.budget_date >= start,
            Transaction.budget_date < end,
            Transaction.booking_date < start,
            Transaction.amount > 0,
        )
    )

    def finish(kind: CategoryKind, sign: int) -> list[CategorySum]:
        # Expenses as positive amounts, sorted descending
        result = []
        for bucket in groups[kind].values():
            bucket.amount *= sign
            for child in bucket.children:
                child.amount *= sign
            bucket.children.sort(key=lambda c: c.amount, reverse=True)
            result.append(bucket)
        return sorted(result, key=lambda c: c.amount, reverse=True)

    # History of the last months
    first_year, first_month = start.year, start.month - history_months + 1
    while first_month < 1:
        first_month += 12
        first_year -= 1
    hist_start = date(first_year, first_month, 1)
    main = aliased(Category)
    month_col = func.to_char(Transaction.budget_date, "YYYY-MM")
    kind_col = func.coalesce(main.kind, Category.kind)
    positive_col = Transaction.amount > literal_column("0")
    hist_rows = db.execute(
        select(month_col, kind_col, positive_col, func.sum(Transaction.amount))
        .outerjoin(Category, Transaction.category_id == Category.id)
        .outerjoin(main, Category.parent_id == main.id)
        .where(*base, Transaction.budget_date >= hist_start, Transaction.budget_date < end)
        .group_by(month_col, kind_col, positive_col)
    ).all()
    history: dict[str, MonthTotal] = {}
    y, m = hist_start.year, hist_start.month
    for _ in range(history_months):
        key = f"{y:04d}-{m:02d}"
        history[key] = MonthTotal(month=key, income=ZERO, expenses=ZERO)
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    for key, kind, positive, amount in hist_rows:
        if kind == CategoryKind.transfer or key not in history:
            continue
        is_income = kind == CategoryKind.income if kind is not None else positive
        if is_income:
            history[key].income += amount
        else:
            history[key].expenses -= amount

    return OverviewOut(
        month=month,
        income=income,
        expenses=-expenses,
        net=income + expenses,
        transfers=transfers,
        income_from_previous_month=income_from_previous_month,
        uncategorized_count=uncategorized_count,
        expense_categories=finish(CategoryKind.expense, -1),
        income_categories=finish(CategoryKind.income, 1),
        history=list(history.values()),
    )
