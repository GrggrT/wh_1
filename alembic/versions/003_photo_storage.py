"""Photo storage paths

Revision ID: 003
Revises: 002
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "shifts",
        sa.Column("start_photo_path", sa.Text(), nullable=True),
    )
    op.add_column(
        "shifts",
        sa.Column("end_photo_path", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("shifts", "end_photo_path")
    op.drop_column("shifts", "start_photo_path")
