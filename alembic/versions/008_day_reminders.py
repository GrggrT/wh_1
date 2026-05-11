"""Phase 5.3: evening day-entry reminders

Adds two columns to users:
- remind_hour_local: int | None — local hour to send reminder (NULL = disabled)
- day_reminder_last_sent: date | None — idempotency for the daily reminder

Revision ID: 008
Revises: 007
Create Date: 2026-05-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "remind_hour_local",
            sa.Integer(),
            nullable=True,
            server_default="19",
        ),
    )
    op.add_column(
        "users",
        sa.Column("day_reminder_last_sent", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "day_reminder_last_sent")
    op.drop_column("users", "remind_hour_local")
