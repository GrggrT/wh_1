"""Initial schema with PostGIS

Revision ID: 001
Revises:
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("tg_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("locale", sa.Text, nullable=False, server_default="ru"),
        sa.Column("hourly_rate", sa.Numeric(10, 2)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "sites",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "polygon",
            geoalchemy2.Geography("POLYGON", srid=4326),
            nullable=True,
        ),
        sa.Column("hourly_rate", sa.Numeric(10, 2)),
        sa.Column("archived_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "shifts",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("site_id", sa.BigInteger, sa.ForeignKey("sites.id"), nullable=True),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True)),
        sa.Column(
            "start_location",
            geoalchemy2.Geography("POINT", srid=4326),
            nullable=True,
        ),
        sa.Column(
            "end_location",
            geoalchemy2.Geography("POINT", srid=4326),
            nullable=True,
        ),
        sa.Column("start_photo_file_id", sa.Text),
        sa.Column("end_photo_file_id", sa.Text),
        sa.Column("note", sa.Text),
        sa.Column("work_type", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # EXCLUDE constraint: max one open shift per user
    op.execute(
        """
        ALTER TABLE shifts ADD CONSTRAINT no_two_open_shifts
        EXCLUDE USING gist (user_id WITH =) WHERE (end_at IS NULL)
        """
    )

    op.create_table(
        "breaks",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("shift_id", sa.BigInteger, sa.ForeignKey("shifts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger, primary_key=True),
        sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("entity_type", sa.Text, nullable=False),
        sa.Column("entity_id", sa.BigInteger, nullable=False),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("diff", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("breaks")
    op.drop_table("shifts")
    op.drop_table("sites")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
    op.execute("DROP EXTENSION IF EXISTS postgis")
