"""Tests for the Phase 5.4 app-settings service (pure logic with mock session)."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from src.services.app_settings import (
    TOGGLE_KEYS,
    SettingsSnapshot,
    get_settings,
    toggle,
)


@dataclass
class FakeAppSettingsRow:
    id: int = 1
    sites_enabled: bool = False
    crews_enabled: bool = False
    geofence_enabled: bool = False
    legacy_clock_inout_enabled: bool = True


@dataclass
class _ScalarOne:
    value: object

    def scalar_one_or_none(self) -> object:
        return self.value


def _session_with_row(row: object | None) -> AsyncMock:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=_ScalarOne(row))
    session.add = lambda obj: None  # plain MagicMock OK; this is fine.
    return session


@pytest.mark.asyncio
async def test_get_settings_reads_existing_row() -> None:
    row = FakeAppSettingsRow(sites_enabled=True)
    session = _session_with_row(row)

    snap = await get_settings(session)

    assert isinstance(snap, SettingsSnapshot)
    assert snap.sites_enabled is True
    assert snap.crews_enabled is False
    assert snap.legacy_clock_inout_enabled is True
    session.flush.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_settings_seeds_row_if_missing() -> None:
    session = _session_with_row(None)
    added: list[object] = []
    session.add = added.append

    snap = await get_settings(session)

    assert len(added) == 1
    # defaults from FakeAppSettingsRow mirror the model defaults
    assert isinstance(snap, SettingsSnapshot)
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_toggle_flips_value() -> None:
    row = FakeAppSettingsRow(sites_enabled=False)
    session = _session_with_row(row)

    snap = await toggle(session, "sites_enabled")

    assert snap.sites_enabled is True
    assert row.sites_enabled is True
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_toggle_flips_back() -> None:
    row = FakeAppSettingsRow(legacy_clock_inout_enabled=True)
    session = _session_with_row(row)

    snap = await toggle(session, "legacy_clock_inout_enabled")

    assert snap.legacy_clock_inout_enabled is False
    assert row.legacy_clock_inout_enabled is False


@pytest.mark.asyncio
async def test_toggle_rejects_unknown_key() -> None:
    row = FakeAppSettingsRow()
    session = _session_with_row(row)

    with pytest.raises(ValueError):
        await toggle(session, "is_admin")


def test_toggle_keys_match_snapshot_fields() -> None:
    """All toggle keys are valid SettingsSnapshot fields (and vice-versa)."""
    snap_fields = set(SettingsSnapshot.__dataclass_fields__.keys())
    assert set(TOGGLE_KEYS) == snap_fields


@pytest.mark.asyncio
async def test_toggle_does_not_touch_other_fields() -> None:
    row = FakeAppSettingsRow(
        sites_enabled=False,
        crews_enabled=True,
        geofence_enabled=False,
        legacy_clock_inout_enabled=True,
    )
    session = _session_with_row(row)

    await toggle(session, "sites_enabled")

    assert row.crews_enabled is True
    assert row.geofence_enabled is False
    assert row.legacy_clock_inout_enabled is True
