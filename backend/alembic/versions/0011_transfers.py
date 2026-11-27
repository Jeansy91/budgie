"""Transfers between own accounts: category source and household settings

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-27 12:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, Sequence[str], None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE cannot run inside a transaction block on older PostgreSQL versions
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE category_source ADD VALUE IF NOT EXISTS 'transfer'")
    op.create_table(
        'transfer_settings',
        sa.Column('household_id', sa.Integer(), nullable=False),
        sa.Column('auto_detect', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('extra_accounts', sa.JSON(), server_default='[]', nullable=False),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('household_id'),
    )
    # Backfill: detect transfers between the household's own accounts in existing data.
    # Runs after the enum value is committed. Additional own IBANs (extra_accounts) do not
    # exist yet at this point, so only IBANs of other accounts of the household count.
    op.execute(
        """
        UPDATE transactions t
        SET category_id = c.id,
            category_source = 'transfer',
            rule_id = NULL,
            category_confidence = NULL,
            suggested_category_id = NULL,
            suggestion_confidence = NULL
        FROM accounts own
        JOIN categories c ON c.household_id = own.household_id AND c.default_key = 'transfers.own_accounts'
        WHERE own.id = t.account_id
          AND t.category_source IS DISTINCT FROM 'manual'
          AND t.counterparty_iban IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM accounts other
              WHERE other.household_id = own.household_id
                AND other.id <> own.id
                AND other.iban IS NOT NULL
                AND upper(replace(other.iban, ' ', '')) = upper(replace(t.counterparty_iban, ' ', ''))
          )
        """
    )


def downgrade() -> None:
    op.drop_table('transfer_settings')
    # PostgreSQL cannot remove an enum value: rebuild the type without it
    op.execute("UPDATE transactions SET category_source = NULL, category_id = NULL WHERE category_source = 'transfer'")
    op.execute("ALTER TYPE category_source RENAME TO category_source_old")
    op.execute("CREATE TYPE category_source AS ENUM ('manual', 'rule', 'model', 'llm')")
    op.execute(
        "ALTER TABLE transactions ALTER COLUMN category_source TYPE category_source "
        "USING category_source::text::category_source"
    )
    op.execute("DROP TYPE category_source_old")
