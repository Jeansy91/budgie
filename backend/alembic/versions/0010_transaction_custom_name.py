"""Transactions: custom name

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-27 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, Sequence[str], None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('custom_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('transactions', 'custom_name')
