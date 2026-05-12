"""Phase 6.9: per-user currency

Adds `users.currency` (TEXT NOT NULL DEFAULT 'PLN'). The bot was hard-coding
the PLN suffix everywhere; this column lets the user pick a different code
in /profile and all money formatting respects the choice.

Revision ID: 012
Revises: 011
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "currency",
            sa.Text(),
            nullable=False,
            server_default="PLN",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "currency")
