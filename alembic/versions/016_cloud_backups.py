"""Phase 7.x: cloud_backups for /backup_to_cloud + /restore_from_cloud

Adds ``cloud_backups`` table — each row points at an XLSX object in
Supabase Storage retrievable by an opaque key. Rows expire on
``expires_at``; a cron sweep can purge stale rows and their blobs.

Revision ID: 016
Revises: 015
Create Date: 2026-05-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cloud_backups",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "owner_user_id", sa.BigInteger(),
            sa.ForeignKey("users.id"), nullable=False,
        ),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=False,
        ),
    )
    op.create_index(
        "ix_cloud_backups_key", "cloud_backups", ["key"], unique=True,
    )
    op.create_index(
        "ix_cloud_backups_owner",
        "cloud_backups", ["owner_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_cloud_backups_owner", table_name="cloud_backups")
    op.drop_index("ix_cloud_backups_key", table_name="cloud_backups")
    op.drop_table("cloud_backups")
