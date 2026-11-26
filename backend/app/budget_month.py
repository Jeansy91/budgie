"""Budget month: the month a transaction counts towards.

Salary usually arrives at the end of a month, but you live on it during the
following month. Budgie therefore moves salary payments received in the last
days of a month to the first of the following month (`Transaction.budget_date`).
The overview, the history and the month filter of the transaction list use this
date; the booking date itself is kept unchanged.

An incoming payment counts as salary if

1. it has been set to "following month" manually (`budget_shift = next`), or
2. it is in one of the salary categories (default: Einnahmen › Gehalt), or
3. the payer matches one of the configured patterns, or
4. auto-detection is enabled and it has no category yet, and either the
   booking text is "Gehalt/Rente" (how ING labels salary payments) or the same
   payer transferred a similar amount at the end of another month.

Transactions in expense or transfer categories are never moved automatically.
`budget_shift = same` keeps a transaction in its booking month.

The budget month is recomputed automatically before every commit that creates
or changes transactions (see `_register_events`), and when the settings are
saved.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import event, inspect, or_, select
from sqlalchemy.orm import Session

from .models import Account, BudgetSettings, BudgetShift, Category, CategoryKind, Transaction

# Booking texts banks use to label wage and salary payments
SALARY_BOOKING_TEXTS = {"gehalt/rente", "lohn/gehalt", "gehalt", "lohn", "rente", "bezüge"}
# How much the amount of a recurring payment may vary
RECURRING_TOLERANCE = Decimal("0.3")
# Smaller payments do not count as salary (e.g. refunds)
RECURRING_MIN_AMOUNT = Decimal("200")

# Attributes whose change can affect the budget month
_RELEVANT = ("booking_date", "amount", "payee", "booking_text", "category_id", "budget_shift", "account_id")


def first_of_next_month(d: date) -> date:
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def in_month_end(d: date, days: int) -> bool:
    """Is the day within the last `days` days of its month?"""
    return days > 0 and d.day > calendar.monthrange(d.year, d.month)[1] - days


def _norm(text: str) -> str:
    return " ".join((text or "").split()).casefold()


def default_salary_categories(db: Session, household_id: int) -> list[int]:
    """Default: the "Gehalt" subcategory of income, otherwise any category named "Gehalt"."""
    candidates = db.scalars(
        select(Category).where(Category.household_id == household_id, Category.name == "Gehalt")
    ).all()
    preferred = [c.id for c in candidates if c.parent is not None and c.parent.kind == CategoryKind.income]
    return preferred or [c.id for c in candidates]


def get_settings(db: Session, household_id: int) -> BudgetSettings:
    settings = db.get(BudgetSettings, household_id)
    if settings is None:
        settings = BudgetSettings(
            household_id=household_id,
            salary_shift_enabled=True,
            salary_shift_days=7,
            salary_category_ids=default_salary_categories(db, household_id),
            salary_payees=[],
            salary_auto_detect=True,
        )
        db.add(settings)
        db.flush()
    return settings


class SalaryDetector:
    """Decides for individual transactions whether they are moved as salary."""

    def __init__(self, db: Session, settings: BudgetSettings, transactions: list[Transaction]):
        self.settings = settings
        categories = db.scalars(select(Category).where(Category.household_id == settings.household_id)).all()
        by_id = {c.id: c for c in categories}
        # Kind of the main category, per category
        self.kind = {c.id: (by_id[c.parent_id].kind if c.parent_id in by_id else c.kind) for c in categories}
        chosen = set(settings.salary_category_ids or [])
        self.salary_categories = {c.id for c in categories if c.id in chosen or c.parent_id in chosen}
        self.payees = [_norm(p) for p in settings.salary_payees or [] if p.strip()]

        # End-of-month payments per payer: (month, amount)
        self.month_end_income: dict[str, list[tuple[tuple[int, int], Decimal]]] = defaultdict(list)
        for t in transactions:
            if t.amount > 0 and t.payee and in_month_end(t.booking_date, settings.salary_shift_days):
                self.month_end_income[_norm(t.payee)].append(((t.booking_date.year, t.booking_date.month), t.amount))

    def _recurring(self, t: Transaction) -> bool:
        if t.amount < RECURRING_MIN_AMOUNT or not t.payee:
            return False
        own_month = (t.booking_date.year, t.booking_date.month)
        for month, amount in self.month_end_income.get(_norm(t.payee), []):
            if month != own_month and abs(amount - t.amount) <= RECURRING_TOLERANCE * max(amount, t.amount):
                return True
        return False

    def is_salary(self, t: Transaction) -> bool:
        if t.amount <= 0:
            return False
        if t.category_id is not None:
            if self.kind.get(t.category_id) in (CategoryKind.expense, CategoryKind.transfer):
                return False
            if t.category_id in self.salary_categories:
                return True
        payee = _norm(t.payee)
        if payee and any(p in payee for p in self.payees):
            return True
        if t.category_id is not None or not self.settings.salary_auto_detect:
            return False
        return _norm(t.booking_text) in SALARY_BOOKING_TEXTS or self._recurring(t)

    def budget_date(self, t: Transaction) -> date:
        if t.budget_shift == BudgetShift.next:
            return first_of_next_month(t.booking_date)
        if t.budget_shift == BudgetShift.same or not self.settings.salary_shift_enabled:
            return t.booking_date
        if in_month_end(t.booking_date, self.settings.salary_shift_days) and self.is_salary(t):
            return first_of_next_month(t.booking_date)
        return t.booking_date


def recompute(db: Session, household_id: int) -> int:
    """Recomputes the budget month of all transactions in the household.

    Returns the number of changed transactions. Does not commit.
    """
    with db.no_autoflush:
        settings = get_settings(db, household_id)
        transactions = db.scalars(
            select(Transaction)
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Account.household_id == household_id,
                or_(
                    Transaction.amount > 0,
                    Transaction.budget_date != Transaction.booking_date,
                    Transaction.budget_shift.is_not(None),
                ),
            )
        ).all()
        detector = SalaryDetector(db, settings, list(transactions))
        changed = 0
        for t in transactions:
            target = detector.budget_date(t)
            if t.budget_date != target:
                t.budget_date = target
                changed += 1
    return changed


# --- Automatic recomputation ----------------------------------------------

_DIRTY_KEY = "budget_month_dirty_accounts"


def _after_flush(session: Session, _flush_context) -> None:
    dirty: set[int] = session.info.setdefault(_DIRTY_KEY, set())
    for obj in session.new:
        if isinstance(obj, Transaction):
            dirty.add(obj.account_id)
    for obj in session.dirty:
        if isinstance(obj, Transaction):
            state = inspect(obj)
            if any(state.attrs[name].history.has_changes() for name in _RELEVANT):
                dirty.add(obj.account_id)


def _before_commit(session: Session) -> None:
    session.flush()
    dirty = session.info.pop(_DIRTY_KEY, set())
    if not dirty:
        return
    households = session.scalars(select(Account.household_id).where(Account.id.in_(dirty)).distinct()).all()
    for household_id in households:
        recompute(session, household_id)
    session.flush()
    # Our own budget month changes must not trigger another round
    session.info.pop(_DIRTY_KEY, None)


def _after_rollback(session: Session) -> None:
    session.info.pop(_DIRTY_KEY, None)


def register_events() -> None:
    if not event.contains(Session, "after_flush", _after_flush):
        event.listen(Session, "after_flush", _after_flush)
        event.listen(Session, "before_commit", _before_commit)
        event.listen(Session, "after_soft_rollback", lambda s, _t: _after_rollback(s))


register_events()
