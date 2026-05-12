"""Phase 6.10b: per-period accounting for advances

Adds ``period_year``/``period_month`` to ``advances``, mirroring the
separation that ``salary_payments`` already has between ``paid_on`` and
the accounting period. Backfills both from the existing ``day`` (this is
what the old "day-windowed" accounting effectively did anyway), then
enforces NOT NULL.

Revision ID: 013
Revises: 012
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "advances",
        sa.Column("period_year", sa.Integer(), nullable=True),
    )
    op.add_column(
        "advances",
        sa.Column("period_month", sa.Integer(), nullable=True),
    )
    op.execute(
        "UPDATE advances "
        "SET period_year = EXTRACT(YEAR FROM day)::int, "
        "    period_month = EXTRACT(MONTH FROM day)::int "
        "WHERE period_year IS NULL OR period_month IS NULL"
    )
    op.alter_column("advances", "period_year", nullable=False)
    op.alter_column("advances", "period_month", nullable=False)
    op.create_index(
        "ix_advances_user_period",
        "advances",
        ["user_id", "period_year", "period_month"],
    )


def downgrade() -> None:
    op.drop_index("ix_advances_user_period", table_name="advances")
    op.drop_column("advances", "period_month")
    op.drop_column("advances", "period_year")
