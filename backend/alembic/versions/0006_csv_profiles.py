"""Saved CSV column mappings for banks without a built-in layout

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-18 23:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, Sequence[str], None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'csv_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('household_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('signature', sa.String(length=64), nullable=False),
        sa.Column('mapping', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('household_id', 'signature'),
    )
    op.create_index(op.f('ix_csv_profiles_household_id'), 'csv_profiles', ['household_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_csv_profiles_household_id'), table_name='csv_profiles')
    op.drop_table('csv_profiles')
