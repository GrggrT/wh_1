"""Phase 7.7: per-user timezone

Adds nullable ``users.timezone`` (IANA name). NULL means "use the bot-wide
default timezone from settings" so existing rows are correct without a
backfill.

Revision ID: 014
Revises: 013
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("timezone", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "timezone")
