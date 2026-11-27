from decimal import Decimal

import pytest

from app.models import Rule, RuleField, RuleMatch, Transaction
from app.rules import matches


def _rule(field: RuleField) -> Rule:
    return Rule(field=field, match_type=RuleMatch.contains, pattern="acme")


OUT = Transaction(payee="ACME GmbH", purpose="Invoice", amount=Decimal("-10.00"))
IN = Transaction(payee="ACME GmbH", purpose="Refund", amount=Decimal("10.00"))


@pytest.mark.parametrize(
    "field,outgoing,incoming",
    [
        (RuleField.payee, True, True),
        (RuleField.recipient, True, False),
        (RuleField.sender, False, True),
        (RuleField.purpose, False, False),
        (RuleField.any, True, True),
    ],
)
def test_rule_direction(field, outgoing, incoming):
    assert matches(_rule(field), OUT) is outgoing
    assert matches(_rule(field), IN) is incoming
