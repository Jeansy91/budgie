"""Rule engine: assigns transactions to a category based on fixed rules."""

from __future__ import annotations

import re
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import CategorySource, Rule, RuleField, RuleMatch, Transaction


def _texts(rule: Rule, t: Transaction) -> list[str]:
    if rule.field == RuleField.recipient:
        # Counterparty of outgoing transactions only
        return [t.payee or ""] if t.amount < 0 else []
    if rule.field == RuleField.sender:
        # Counterparty of incoming transactions only
        return [t.payee or ""] if t.amount > 0 else []
    if rule.field == RuleField.payee:
        return [t.payee or ""]
    if rule.field == RuleField.purpose:
        return [t.purpose or ""]
    return [t.payee or "", t.purpose or ""]


def matches(rule: Rule, t: Transaction) -> bool:
    pattern = rule.pattern.strip()
    if not pattern:
        return False
    for text in _texts(rule, t):
        if rule.match_type == RuleMatch.regex:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error:
                return False
            continue
        a, b = " ".join(text.split()).casefold(), " ".join(pattern.split()).casefold()
        if rule.match_type == RuleMatch.contains and b in a:
            return True
        if rule.match_type == RuleMatch.equals and a == b:
            return True
        if rule.match_type == RuleMatch.starts_with and a.startswith(b):
            return True
    return False


def active_rules(db: Session, household_id: int) -> list[Rule]:
    return list(
        db.scalars(
            select(Rule)
            .where(Rule.household_id == household_id, Rule.active.is_(True))
            .order_by(Rule.priority.desc(), Rule.id)
        )
    )


def first_match(rules: Iterable[Rule], t: Transaction) -> Rule | None:
    return next((r for r in rules if matches(r, t)), None)


def apply_rules(
    db: Session, household_id: int, transactions: Iterable[Transaction], overwrite_rule_results: bool = False
) -> int:
    """Applies rules. Manual assignments are never overwritten, AI assignments are.

    Without `overwrite_rule_results`, only uncategorized transactions are
    processed. With the flag, results of earlier rules are recomputed as well.
    Returns the number of newly assigned transactions.
    """
    rules = active_rules(db, household_id)
    changed = 0
    for t in transactions:
        if t.category_source == CategorySource.manual:
            continue
        # Rules take precedence over the AI; earlier rule results are only recomputed with the flag
        ai = t.category_source in (CategorySource.model, CategorySource.llm)
        if (
            t.category_id is not None
            and not ai
            and not (overwrite_rule_results and t.category_source == CategorySource.rule)
        ):
            continue
        rule = first_match(rules, t)
        if rule is None:
            if overwrite_rule_results and t.category_source == CategorySource.rule:
                t.category_id, t.category_source, t.rule_id = None, None, None
            continue
        if t.category_id != rule.category_id or t.rule_id != rule.id:
            t.category_id, t.category_source, t.rule_id = rule.category_id, CategorySource.rule, rule.id
            t.category_confidence = None
            t.suggested_category_id, t.suggestion_confidence = None, None
            changed += 1
    return changed
