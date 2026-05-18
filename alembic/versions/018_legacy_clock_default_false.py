"""Default `legacy_clock_inout_enabled` to false for new app_settings rows.

The bot ships in Phase 5 simplified mode by default: type hours per day,
no shifts. The original `server_default="true"` was a backwards-compat
hint for upgrades from the pre-simple-mode era; that era is over. New
installs should be clean — no /quick_start, /shifts, etc. in the TG
slash menu unless the owner deliberately opts in via /settings.

Existing rows are not touched here; flipping live data is a deployment
concern, not a schema one.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "018_legacy_clock_default_false"
down_revision = "017_enable_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "app_settings",
        "legacy_clock_inout_enabled",
        server_default=sa.text("false"),
    )


def downgrade() -> None:
    op.alter_column(
        "app_settings",
        "legacy_clock_inout_enabled",
        server_default=sa.text("true"),
    )
