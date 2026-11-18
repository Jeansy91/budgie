"""Budget month: assign end-of-month salary to the following month

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18 18:30:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0003'
down_revision: Union[str, Sequence[str], None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('budget_settings',
    sa.Column('household_id', sa.Integer(), nullable=False),
    sa.Column('salary_shift_enabled', sa.Boolean(), nullable=False),
    sa.Column('salary_shift_days', sa.Integer(), nullable=False),
    sa.Column('salary_category_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
    sa.Column('salary_payees', postgresql.ARRAY(sa.String(length=255)), nullable=False),
    sa.Column('salary_auto_detect', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('household_id')
    )
    budget_shift = postgresql.ENUM('next', 'same', name='budget_shift')
    budget_shift.create(op.get_bind())
    op.add_column('transactions', sa.Column('budget_date', sa.Date(), nullable=True))
    op.add_column('transactions', sa.Column('budget_shift', budget_shift, nullable=True))
    op.execute('UPDATE transactions SET budget_date = booking_date')
    # Move existing salaries (Einnahmen › Gehalt) from the last 7 days of a
    # month to the following month right away. The remaining detection (booking
    # text, recurring payments) applies on the next import or when the settings
    # are saved.
    op.execute("""
        INSERT INTO budget_settings (household_id, salary_shift_enabled, salary_shift_days,
                                     salary_category_ids, salary_payees, salary_auto_detect)
        SELECT h.id, true, 7,
               COALESCE((SELECT array_agg(c.id) FROM categories c JOIN categories p ON p.id = c.parent_id
                         WHERE c.household_id = h.id AND c.name = 'Gehalt' AND p.kind = 'income'), '{}'),
               '{}', true
        FROM households h
    """)
    op.execute("""
        UPDATE transactions t
        SET budget_date = (date_trunc('month', t.booking_date) + interval '1 month')::date
        FROM accounts a, budget_settings s
        WHERE a.id = t.account_id AND s.household_id = a.household_id
          AND t.amount > 0
          AND t.category_id = ANY (s.salary_category_ids)
          AND t.booking_date > (date_trunc('month', t.booking_date) + interval '1 month')::date - 1 - 7
    """)
    op.alter_column('transactions', 'budget_date', nullable=False)
    op.create_index(op.f('ix_transactions_budget_date'), 'transactions', ['budget_date'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_transactions_budget_date'), table_name='transactions')
    op.drop_column('transactions', 'budget_shift')
    op.drop_column('transactions', 'budget_date')
    postgresql.ENUM(name='budget_shift').drop(op.get_bind())
    op.drop_table('budget_settings')
