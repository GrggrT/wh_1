"""Tests for /range inline picker preset date math."""

from __future__ import annotations

from datetime import date

from src.bot.handlers.accounting import _range_preset_dates

# 2026-05-12 is a Tuesday.
_TODAY = date(2026, 5, 12)


def test_preset_this_week_runs_mon_to_sun() -> None:
    rng = _range_preset_dates("tw", _TODAY)
    assert rng == (date(2026, 5, 11), date(2026, 5, 17))


def test_preset_last_week_runs_mon_to_sun() -> None:
    rng = _range_preset_dates("lw", _TODAY)
    assert rng == (date(2026, 5, 4), date(2026, 5, 10))


def test_preset_this_month_covers_full_month() -> None:
    rng = _range_preset_dates("tm", _TODAY)
    assert rng == (date(2026, 5, 1), date(2026, 5, 31))


def test_preset_last_month_covers_full_prev_month() -> None:
    rng = _range_preset_dates("lm", _TODAY)
    assert rng == (date(2026, 4, 1), date(2026, 4, 30))


def test_preset_last_7_days_ends_today_inclusive() -> None:
    rng = _range_preset_dates("d7", _TODAY)
    assert rng == (date(2026, 5, 6), date(2026, 5, 12))


def test_preset_last_30_days_ends_today_inclusive() -> None:
    rng = _range_preset_dates("d30", _TODAY)
    assert rng == (date(2026, 4, 13), date(2026, 5, 12))


def test_preset_last_month_handles_january_rollback() -> None:
    rng = _range_preset_dates("lm", date(2026, 1, 5))
    assert rng == (date(2025, 12, 1), date(2025, 12, 31))


def test_preset_unknown_key_returns_none() -> None:
    assert _range_preset_dates("nope", _TODAY) is None
