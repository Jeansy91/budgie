"""Transaction details: SEPA fields of the counterparty

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-18 20:30:00

"""
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, Sequence[str], None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of app.fints.convert.IBAN_LENGTHS at the time of this migration
IBAN_LENGTHS = {
    "AT": 20, "BE": 16, "BG": 22, "CH": 21, "CY": 28, "CZ": 24, "DE": 22, "DK": 18, "EE": 20,
    "ES": 24, "FI": 18, "FR": 27, "GB": 22, "GR": 27, "HR": 21, "HU": 28, "IE": 22, "IS": 26,
    "IT": 27, "LI": 21, "LT": 20, "LU": 20, "LV": 21, "MC": 27, "MT": 31, "NL": 18, "NO": 15,
    "PL": 28, "PT": 25, "RO": 24, "SE": 24, "SI": 19, "SK": 24, "SM": 27,
}
IBAN_START = re.compile(r"([A-Z]{2})(\d{2})")


def upgrade() -> None:
    op.add_column('transactions', sa.Column('counterparty_iban', sa.String(length=34), nullable=True))
    op.add_column('transactions', sa.Column('counterparty_bic', sa.String(length=11), nullable=True))
    op.add_column('transactions', sa.Column('mandate_id', sa.String(length=35), nullable=True))
    op.add_column('transactions', sa.Column('creditor_id', sa.String(length=35), nullable=True))
    op.add_column('transactions', sa.Column('end_to_end_ref', sa.String(length=35), nullable=True))

    # MT940 delivers the counterparty IBAN glued to the front of the name
    # ("DE89…Stadtwerke"). Move it to its own column for transactions that were
    # already synced via FinTS. The fingerprint (dedup_hash) stays unchanged.
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT t.id, t.payee FROM transactions t JOIN imports i ON i.id = t.import_id "
        "WHERE i.source = 'fints' AND t.payee ~ '^[A-Z]{2}[0-9]{2}'"
    )).all()
    for tx_id, payee in rows:
        m = IBAN_START.match(payee)
        length = IBAN_LENGTHS.get(m.group(1)) if m else None
        if not length or len(payee) < length or not payee[:length].isalnum():
            continue
        conn.execute(
            sa.text("UPDATE transactions SET counterparty_iban = :iban, payee = :payee WHERE id = :id"),
            {"iban": payee[:length], "payee": payee[length:].strip(), "id": tx_id},
        )


def downgrade() -> None:
    op.drop_column('transactions', 'end_to_end_ref')
    op.drop_column('transactions', 'creditor_id')
    op.drop_column('transactions', 'mandate_id')
    op.drop_column('transactions', 'counterparty_bic')
    op.drop_column('transactions', 'counterparty_iban')
