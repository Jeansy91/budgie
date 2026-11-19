import re

from fastapi import APIRouter, status
from sqlalchemy import func, select

from ..deps import DB, CurrentUser, visible_account_ids
from ..i18n import http_error
from ..models import Rule, Transaction, User
from ..rules import apply_rules
from ..schemas import ApplyRulesIn, ApplyRulesOut, RuleIn, RuleOut, RulePatch
from .categories import get_category

router = APIRouter(prefix="/rules", tags=["rules"])


def _validate(db: DB, user: User, rule: Rule) -> None:
    get_category(db, user, rule.category_id)
    if rule.match_type.value == "regex":
        try:
            re.compile(rule.pattern)
        except re.error as exc:
            raise http_error(status.HTTP_400_BAD_REQUEST, "rules.invalid_regex", error=exc) from None


def get_rule(db: DB, user: User, rule_id: int) -> Rule:
    rule = db.get(Rule, rule_id)
    if rule is None or rule.household_id != user.household_id:
        raise http_error(status.HTTP_404_NOT_FOUND, "rules.not_found")
    return rule


def rule_out(db: DB, rule: Rule) -> RuleOut:
    out = RuleOut.model_validate(rule)
    out.match_count = db.scalar(select(func.count(Transaction.id)).where(Transaction.rule_id == rule.id)) or 0
    return out


def household_transactions(db: DB, user: User):
    return db.scalars(select(Transaction).where(Transaction.account_id.in_(visible_account_ids(user)))).all()


@router.get("", response_model=list[RuleOut])
def list_rules(db: DB, user: CurrentUser):
    rules = db.scalars(
        select(Rule).where(Rule.household_id == user.household_id).order_by(Rule.priority.desc(), Rule.id)
    ).all()
    return [rule_out(db, r) for r in rules]


@router.post("", response_model=RuleOut, status_code=201)
def create_rule(data: RuleIn, db: DB, user: CurrentUser, apply: bool = True):
    rule = Rule(household_id=user.household_id, created_by=user.id, **data.model_dump())
    _validate(db, user, rule)
    db.add(rule)
    db.flush()
    if apply:
        apply_rules(db, user.household_id, household_transactions(db, user))
    db.commit()
    return rule_out(db, rule)


@router.patch("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, data: RulePatch, db: DB, user: CurrentUser):
    rule = get_rule(db, user, rule_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rule, key, value)
    _validate(db, user, rule)
    db.commit()
    return rule_out(db, rule)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: DB, user: CurrentUser):
    db.delete(get_rule(db, user, rule_id))
    db.commit()


@router.post("/apply", response_model=ApplyRulesOut)
def apply_all(data: ApplyRulesIn, db: DB, user: CurrentUser):
    """Re-applies all rules. Manual assignments are left untouched."""
    changed = apply_rules(db, user.household_id, household_transactions(db, user), data.overwrite_rule_results)
    db.commit()
    return ApplyRulesOut(changed=changed)
