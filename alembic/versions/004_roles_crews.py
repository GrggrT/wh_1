"""Roles, crews, and invite codes

Revision ID: 004
Revises: 003
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "role", sa.Text(), nullable=False, server_default="worker",
        ),
    )

    op.create_table(
        "crews",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column(
            "foreman_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.add_column(
        "users",
        sa.Column(
            "crew_id",
            sa.BigInteger,
            sa.ForeignKey("crews.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "invite_codes",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column(
            "crew_id",
            sa.BigInteger,
            sa.ForeignKey("crews.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_by_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "used_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "used_by_user_id",
            sa.BigInteger,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("invite_codes")
    op.drop_column("users", "crew_id")
    op.drop_table("crews")
    op.drop_column("users", "role")
