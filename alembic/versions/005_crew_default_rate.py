"""Crew default hourly rate

Revision ID: 005
Revises: 004
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crews",
        sa.Column("default_hourly_rate", sa.Numeric(10, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("crews", "default_hourly_rate")
