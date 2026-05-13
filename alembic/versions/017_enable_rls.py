"""Enable Row-Level Security on all application tables.

The bot connects to Postgres directly with the privileged ``postgres`` /
``service_role`` role, which bypasses RLS. We don't use Supabase's Data
API (``/rest/v1/``, ``supabase-js``) at all — but those endpoints are
still listening for the ``anon`` and ``authenticated`` roles. If the
anon key ever leaks (or someone trips on it in the project settings),
every table becomes readable without auth.

The Supabase-recommended fix for backend-only projects is to enable RLS
without adding any policies. With RLS on + zero policies:

* ``postgres`` and ``service_role`` bypass RLS → bot/admin keep working
* ``anon`` and ``authenticated`` are denied all rows → REST API returns 0

This also resolves the ``sensitive_columns_exposed`` advisor on
``share_tokens.token`` because the row is no longer reachable.

Skipped on purpose:

* ``spatial_ref_sys`` — PostGIS system table, ownership may not be ours
* ``postgis`` / ``btree_gist`` in public schema — moving extensions is
  destructive and not worth the risk
* PostGIS ``st_estimatedextent(*)`` SECURITY DEFINER functions — built-in

Revision ID: 017
Revises: 016
Create Date: 2026-05-13

"""
from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TABLES: tuple[str, ...] = (
    "users",
    "crews",
    "sites",
    "shifts",
    "breaks",
    "day_entries",
    "advances",
    "salary_payments",
    "audit_log",
    "invite_codes",
    "app_settings",
    "share_tokens",
    "cloud_backups",
    "alembic_version",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY")
