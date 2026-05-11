"""Tests for the Phase 5.5 feature-gate middleware (pure logic).

We test the command-extraction helper and the `is_allowed` decision
function directly. The middleware's session/DB plumbing is exercised by
existing integration paths.
"""

from __future__ import annotations

from src.bot.middlewares.features import (
    COMMAND_FEATURE_MAP,
    _extract_command_name,
    is_allowed,
    required_feature,
)
from src.services.app_settings import TOGGLE_KEYS, SettingsSnapshot


def _snap(**overrides: bool) -> SettingsSnapshot:
    defaults: dict[str, bool] = {
        "sites_enabled": False,
        "crews_enabled": False,
        "geofence_enabled": False,
        "legacy_clock_inout_enabled": False,
    }
    defaults.update(overrides)
    return SettingsSnapshot(**defaults)  # type: ignore[arg-type]


def test_extract_command_strips_slash_and_bot_suffix() -> None:
    assert _extract_command_name("/h") == "h"
    assert _extract_command_name("/h 8") == "h"
    assert _extract_command_name("/quick_start@my_bot") == "quick_start"
    assert _extract_command_name("/h@bot 8.5") == "h"


def test_extract_command_returns_none_for_non_commands() -> None:
    assert _extract_command_name(None) is None
    assert _extract_command_name("") is None
    assert _extract_command_name("hello") is None
    assert _extract_command_name("привет /h") is None


def test_extract_command_handles_just_slash() -> None:
    assert _extract_command_name("/") is None


def test_always_allowed_commands_have_no_feature() -> None:
    """Core simple-mode commands must never be gated."""
    for cmd in (
        "start",
        "help",
        "cancel",
        "h",
        "my_days",
        "edit_day",
        "salary",
        "my_advances",
        "advance",
        "whoami",
        "my_rate",
        "set_rate",
        "remind_on",
        "remind_off",
        "settings",
        "status",
        "stats",
        "admin_audit",
        "digest",
        "digest_week",
        "digest_month",
    ):
        assert required_feature(cmd) is None, f"{cmd} should always be allowed"


def test_is_allowed_when_feature_enabled() -> None:
    snap = _snap(legacy_clock_inout_enabled=True)
    assert is_allowed("quick_start", snap) is True
    assert is_allowed("my_open", snap) is True
    assert is_allowed("today", snap) is True


def test_is_allowed_blocks_when_feature_disabled() -> None:
    snap = _snap()  # everything off
    assert is_allowed("quick_start", snap) is False
    assert is_allowed("sites", snap) is False
    assert is_allowed("geofence_set", snap) is False
    assert is_allowed("crew", snap) is False


def test_is_allowed_passes_through_ungated_commands() -> None:
    snap = _snap()
    for cmd in ("h", "salary", "settings", "start", "help"):
        assert is_allowed(cmd, snap) is True


def test_each_mapped_feature_is_a_known_toggle() -> None:
    """Every value in the command→feature map must be a real SettingsSnapshot field."""
    valid = set(TOGGLE_KEYS)
    for cmd, feature in COMMAND_FEATURE_MAP.items():
        assert feature in valid, f"{cmd} → {feature} is not a known toggle"


def test_feature_map_covers_expected_commands() -> None:
    """Spot-check coverage so a refactor doesn't accidentally drop gating."""
    assert COMMAND_FEATURE_MAP["quick_start"] == "legacy_clock_inout_enabled"
    assert COMMAND_FEATURE_MAP["sites"] == "sites_enabled"
    assert COMMAND_FEATURE_MAP["geofence_set"] == "geofence_enabled"
    assert COMMAND_FEATURE_MAP["crew"] == "crews_enabled"
    assert COMMAND_FEATURE_MAP["crew_salary"] == "crews_enabled"
