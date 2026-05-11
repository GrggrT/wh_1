"""Phase 6.3: onboarding wizard

Adds `users.onboarded_at` — the timestamp when a worker finished the
first-run wizard. NULL = wizard not yet completed. Existing rows are
backfilled with the current time so users who already use the bot aren't
sent through the wizard again.

Revision ID: 010
Revises: 009
Create Date: 2026-05-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "onboarded_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Existing users have been using the bot already — mark them as onboarded
    # so they don't get the first-run wizard. New rows default to NULL.
    op.execute("UPDATE users SET onboarded_at = now() WHERE onboarded_at IS NULL")


def downgrade() -> None:
    op.drop_column("users", "onboarded_at")
