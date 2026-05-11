"""Phase 5.4: global product-mode toggles.

Single-tenant bot → one row at id=1. The row is seeded by the migration; if
it is missing for any reason (manual edits, tests against a stub DB) we
recreate it on first read.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import AppSettings

_ROW_ID = 1

# Allowed toggle attribute names. Keep this tight so /settings can't be
# tricked into flipping arbitrary columns.
TOGGLE_KEYS: tuple[str, ...] = (
    "sites_enabled",
    "crews_enabled",
    "geofence_enabled",
    "legacy_clock_inout_enabled",
)


@dataclass(frozen=True)
class SettingsSnapshot:
    """Read-only view of the current toggle values."""

    sites_enabled: bool
    crews_enabled: bool
    geofence_enabled: bool
    legacy_clock_inout_enabled: bool

    @classmethod
    def from_row(cls, row: AppSettings) -> SettingsSnapshot:
        return cls(
            sites_enabled=row.sites_enabled,
            crews_enabled=row.crews_enabled,
            geofence_enabled=row.geofence_enabled,
            legacy_clock_inout_enabled=row.legacy_clock_inout_enabled,
        )


async def _get_row(session: AsyncSession) -> AppSettings:
    row = (
        await session.execute(select(AppSettings).where(AppSettings.id == _ROW_ID))
    ).scalar_one_or_none()
    if row is None:
        row = AppSettings(id=_ROW_ID)
        session.add(row)
        await session.flush()
    return row


async def get_settings(session: AsyncSession) -> SettingsSnapshot:
    row = await _get_row(session)
    return SettingsSnapshot.from_row(row)


async def toggle(session: AsyncSession, key: str) -> SettingsSnapshot:
    """Flip a single toggle and return the new snapshot.

    Raises ValueError for unknown keys.
    """
    if key not in TOGGLE_KEYS:
        raise ValueError(f"unknown toggle: {key}")
    row = await _get_row(session)
    current = bool(getattr(row, key))
    setattr(row, key, not current)
    await session.flush()
    return SettingsSnapshot.from_row(row)
