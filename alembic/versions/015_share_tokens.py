"""Phase 7.x: share_tokens for cross-account /restore_from

Adds ``share_tokens`` table backing the bot's /share_backup +
/restore_from flow. Rows are one-shot (unique ``token``), expire
on ``expires_at``, and record who redeemed them.

Revision ID: 015
Revises: 014
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "share_tokens",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("token", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "source_user_id", sa.BigInteger(),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "redeemed_at", sa.DateTime(timezone=True), nullable=True,
        ),
        sa.Column(
            "redeemed_by_user_id", sa.BigInteger(),
            sa.ForeignKey("users.id"), nullable=True,
        ),
    )
    op.create_index(
        "ix_share_tokens_token", "share_tokens", ["token"], unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_share_tokens_token", table_name="share_tokens")
    op.drop_table("share_tokens")
