"""Rules: separate fields for sender (incoming) and recipient (outgoing)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-27 12:00:00

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, Sequence[str], None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New enum values cannot be added inside a transaction block
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE rule_field ADD VALUE IF NOT EXISTS 'recipient'")
        op.execute("ALTER TYPE rule_field ADD VALUE IF NOT EXISTS 'sender'")


def downgrade() -> None:
    op.execute("UPDATE rules SET field = 'payee' WHERE field IN ('recipient', 'sender')")
    op.execute("ALTER TYPE rule_field RENAME TO rule_field_old")
    op.execute("CREATE TYPE rule_field AS ENUM ('payee', 'purpose', 'any')")
    op.execute("ALTER TABLE rules ALTER COLUMN field DROP DEFAULT")
    op.execute("ALTER TABLE rules ALTER COLUMN field TYPE rule_field USING field::text::rule_field")
    op.execute("DROP TYPE rule_field_old")
