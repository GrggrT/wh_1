"""Phase 5.4: app_settings (global feature toggles)

Single-row table (id=1) holding the bot's product-mode toggles. Defaults
favour the simplified Phase 5 flow (everything advanced OFF), but the
existing clock-in/out flow is kept ON to avoid breaking the running
deployment until the cutover.

Revision ID: 009
Revises: 008
Create Date: 2026-05-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "sites_enabled", sa.Boolean(), nullable=False, server_default="false",
        ),
        sa.Column(
            "crews_enabled", sa.Boolean(), nullable=False, server_default="false",
        ),
        sa.Column(
            "geofence_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column(
            "legacy_clock_inout_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Seed the singleton row so callers can always assume id=1 exists.
    op.execute(
        "INSERT INTO app_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING",
    )


def downgrade() -> None:
    op.drop_table("app_settings")
