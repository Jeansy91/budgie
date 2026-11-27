"""Transfers between own accounts.

A transaction whose counterparty IBAN belongs to another own account is a
transfer. Own accounts are the household's accounts plus additional IBANs
the user entered (e.g. a savings account at another bank, not tracked in
Budgie). Detected transfers get the transfer category with the source
`transfer`. Manual assignments are never overwritten; detection runs before
the rules and the AI and is not touched by them.
"""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ai import service as ai
from .importers.common import normalize_iban
from .models import Account, Category, CategoryKind, CategorySource, Transaction, TransferSettings
from .rules import apply_rules

TARGET_KEY = "transfers.own_accounts"


def get_settings(db: Session, household_id: int) -> TransferSettings:
    settings = db.get(TransferSettings, household_id)
    if settings is None:
        settings = TransferSettings(household_id=household_id, auto_detect=True, extra_accounts=[])
        db.add(settings)
        db.flush()
    return settings


def is_valid_iban(iban: str) -> bool:
    """Basic IBAN check on a normalized value: format and mod-97 checksum."""
    if not (15 <= len(iban) <= 34) or not iban.isascii() or not iban.isalnum():
        return False
    if not (iban[:2].isalpha() and iban[2:4].isdigit()):
        return False
    rearranged = iban[4:] + iban[:4]
    return int("".join(str(int(c, 36)) for c in rearranged)) % 97 == 1


def own_ibans(db: Session, household_id: int) -> set[str]:
    """All IBANs of the household's accounts plus the additional own IBANs, normalized."""
    ibans = {
        normalize_iban(i) for i in db.scalars(select(Account.iban).where(Account.household_id == household_id)) if i
    }
    ibans.update(normalize_iban(a["iban"]) for a in get_settings(db, household_id).extra_accounts if a.get("iban"))
    return ibans


def target_category(db: Session, household_id: int) -> Category | None:
    """The category detected transfers are assigned to, or None if there is none."""
    default = db.scalar(
        select(Category).where(Category.household_id == household_id, Category.default_key == TARGET_KEY)
    )
    if default is not None:
        return default
    main = select(Category.id).where(
        Category.household_id == household_id, Category.parent_id.is_(None), Category.kind == CategoryKind.transfer
    )
    sub = db.scalar(
        select(Category)
        .where(Category.household_id == household_id, Category.parent_id.in_(main))
        .order_by(Category.sort_order, Category.id)
        .limit(1)
    )
    if sub is not None:
        return sub
    # A transfer main category without children
    for category in db.scalars(
        select(Category)
        .where(
            Category.household_id == household_id, Category.parent_id.is_(None), Category.kind == CategoryKind.transfer
        )
        .order_by(Category.sort_order, Category.id)
    ):
        has_children = db.scalar(select(Category.id).where(Category.parent_id == category.id).limit(1))
        if has_children is None:
            return category
    return None


def _account_ibans(db: Session, household_id: int) -> dict[int, str]:
    rows = db.execute(select(Account.id, Account.iban).where(Account.household_id == household_id))
    return {i: normalize_iban(iban) for i, iban in rows if iban}


def _is_transfer(t: Transaction, own: set[str], account_ibans: dict[int, str]) -> bool:
    if not t.counterparty_iban:
        return False
    iban = normalize_iban(t.counterparty_iban)
    return iban in own and iban != account_ibans.get(t.account_id)


def _mark(t: Transaction, category: Category) -> bool:
    """Marks a transaction as detected transfer. Returns whether anything changed."""
    changed = t.category_id != category.id or t.category_source != CategorySource.transfer
    t.category_id, t.category_source, t.rule_id = category.id, CategorySource.transfer, None
    t.category_confidence = None
    t.suggested_category_id, t.suggestion_confidence = None, None
    return changed


def detect_transfers(db: Session, household_id: int, transactions: Iterable[Transaction]) -> int:
    """Marks transactions with the IBAN of another own account as transfers.

    Manual assignments are skipped. Returns the number of newly marked transactions.
    """
    if not get_settings(db, household_id).auto_detect:
        return 0
    category = target_category(db, household_id)
    if category is None:
        return 0
    own = own_ibans(db, household_id)
    account_ibans = _account_ibans(db, household_id)
    changed = 0
    for t in transactions:
        if t.category_source == CategorySource.manual or not _is_transfer(t, own, account_ibans):
            continue
        changed += _mark(t, category)
    return changed


def redetect(db: Session, household_id: int) -> int:
    """Recomputes the detected transfers of all household transactions.

    Matching transactions are marked, detected transfers that no longer match
    (IBAN removed, detection turned off) are uncategorized and then categorized
    like a fresh import would. Returns the number of changed transactions.
    """
    settings = get_settings(db, household_id)
    category = target_category(db, household_id) if settings.auto_detect else None
    own = own_ibans(db, household_id)
    account_ibans = _account_ibans(db, household_id)
    accounts = select(Account.id).where(Account.household_id == household_id)
    changed = 0
    released: list[Transaction] = []
    for t in db.scalars(select(Transaction).where(Transaction.account_id.in_(accounts))):
        if t.category_source == CategorySource.manual:
            continue
        if category is not None and _is_transfer(t, own, account_ibans):
            changed += _mark(t, category)
        elif t.category_source == CategorySource.transfer:
            t.category_id, t.category_source, t.rule_id = None, None, None
            released.append(t)
            changed += 1
    if released:
        db.flush()
        apply_rules(db, household_id, released)
        result = ai.categorize(db, household_id, released)
        if result.unsure_ids:
            ids = result.unsure_ids
            ai.after_commit(db, lambda: ai.schedule_llm(household_id, ids))
    return changed
