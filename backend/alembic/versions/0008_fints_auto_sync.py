"""FinTS: automatic fetching (opt-in encrypted PIN, interval, pause state)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-27 10:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('bank_connections', sa.Column('pin_enc', sa.Text(), nullable=True))
    op.add_column('bank_connections', sa.Column('auto_sync_enabled', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column('bank_connections', sa.Column('auto_sync_interval_hours', sa.Integer(), server_default='12', nullable=False))
    op.add_column('bank_connections', sa.Column('next_auto_sync_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('bank_connections', sa.Column('auto_sync_paused_reason', sa.Text(), nullable=True))
    op.add_column('bank_connections', sa.Column('auto_sync_failures', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    for column in ('auto_sync_failures', 'auto_sync_paused_reason', 'next_auto_sync_at',
                   'auto_sync_interval_hours', 'auto_sync_enabled', 'pin_enc'):
        op.drop_column('bank_connections', column)
