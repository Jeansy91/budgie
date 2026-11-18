"""Shared storage path for all import sources (CSV file and FinTS sync).

New transactions are created, known ones are skipped, and afterwards the rules
and the AI categorization are applied.

Budgie detects duplicates in two stages:

1. **Same fingerprint** (`dedup_hash`): date, amount, payee and purpose match.
   This applies when the same source delivers the same period again.
2. **Different source, same day and amount:** the CSV export and FinTS do not
   always format payee and purpose the same way. If a transaction with the
   same amount on the same day already exists from the other source, the new
   one is treated as already present. Matching is counted per transaction: two
   equal amounts on one day in the CSV cover two in the FinTS sync, no more.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..ai import service as ai
from ..models import Account, ImportBatch, Transaction
from ..rules import apply_rules
from .ing_csv import ParsedTransaction


def store_transactions(
    db: Session,
    *,
    household_id: int,
    user_id: int | None,
    account: Account,
    parsed: list[ParsedTransaction],
    source: str,
    filename: str | None = None,
) -> ImportBatch:
    """Stores the transactions of an import. Does not commit; the caller does."""
    batch = ImportBatch(
        account_id=account.id, user_id=user_id, source=source, filename=filename, rows_total=len(parsed)
    )
    db.add(batch)
    db.flush()

    existing_hashes: set[str] = set()
    # (day, amount) → number of transactions from another source
    other_source: Counter[tuple] = Counter()
    other_source_hashes: set[str] = set()
    if parsed:
        rows = db.execute(
            select(Transaction.dedup_hash, Transaction.booking_date, Transaction.amount, ImportBatch.source)
            .outerjoin(ImportBatch, ImportBatch.id == Transaction.import_id)
            .where(
                Transaction.account_id == account.id,
                Transaction.booking_date >= min(p.booking_date for p in parsed),
                Transaction.booking_date <= max(p.booking_date for p in parsed),
            )
        ).all()
        for h, booking_date, amount, row_source in rows:
            if row_source != source:
                other_source[_key(booking_date, amount)] += 1
                other_source_hashes.add(h)
        existing_hashes = set(db.scalars(select(Transaction.dedup_hash).where(Transaction.account_id == account.id)))

    # Exact matches from the other source use up their slot in the counter first
    for p in parsed:
        if p.dedup_hash in other_source_hashes:
            other_source[_key(p.booking_date, p.amount)] -= 1

    new: list[Transaction] = []
    for p in parsed:
        if p.dedup_hash in existing_hashes:
            continue
        key = _key(p.booking_date, p.amount)
        if other_source[key] > 0:
            other_source[key] -= 1
            continue
        existing_hashes.add(p.dedup_hash)
        new.append(
            Transaction(
                account_id=account.id,
                booking_date=p.booking_date,
                value_date=p.value_date,
                amount=p.amount,
                currency=p.currency,
                payee=p.payee[:255],
                booking_text=p.booking_text[:100],
                purpose=p.purpose,
                balance_after=p.balance_after,
                counterparty_iban=_clip(p.counterparty_iban, 34),
                counterparty_bic=_clip(p.counterparty_bic, 11),
                mandate_id=_clip(p.mandate_id, 35),
                creditor_id=_clip(p.creditor_id, 35),
                end_to_end_ref=_clip(p.end_to_end_ref, 35),
                import_id=batch.id,
                dedup_hash=p.dedup_hash,
            )
        )
    db.add_all(new)
    db.flush()

    batch.rows_imported = len(new)
    batch.rows_duplicate = batch.rows_total - len(new)
    by_rules = apply_rules(db, household_id, new)
    # Whatever no rule matches is categorized by the AI. Uncertain cases go to
    # the language model in the background after the commit, if configured.
    result = ai.categorize(db, household_id, new)
    batch.rows_categorized = by_rules + result.assigned
    if result.unsure_ids:
        ids = result.unsure_ids
        ai.after_commit(db, lambda: ai.schedule_llm(household_id, ids))
    return batch


def _key(booking_date, amount) -> tuple:
    return booking_date, Decimal(amount).quantize(Decimal("0.01"))


def _clip(value: str | None, length: int) -> str | None:
    return value[:length] if value else None
