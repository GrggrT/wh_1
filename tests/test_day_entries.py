"""Tests for the Phase 5.1 day-entries service (pure logic; no DB)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from src.services.day_entries import (
    DAY_OFF,
    MAX_HOURS,
    MIN_WORK_HOURS,
    QUICK_HOURS,
    SUGGEST_MIN_OCCURRENCES,
    SUGGEST_WINDOW_DAYS,
    format_hours,
    is_day_off,
    parse_hours,
    personalized_picks,
    quick_pick_values,
    smart_suggest,
)


@dataclass
class FakeDayEntry:
    """Stand-in for the SQLAlchemy DayEntry — `smart_suggest` only reads .hours."""

    hours: Decimal
    day: date


def _entry(hours: str, days_ago: int) -> FakeDayEntry:
    return FakeDayEntry(
        hours=Decimal(hours), day=date.today() - timedelta(days=days_ago),
    )


# ---- parse_hours -----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("8", Decimal("8.00")),
        ("8.5", Decimal("8.50")),
        ("8,5", Decimal("8.50")),
        ("  10  ", Decimal("10.00")),
        ("0.25", Decimal("0.25")),
        ("24", Decimal("24.00")),
    ],
)
def test_parse_hours_accepts_valid(raw: str, expected: Decimal) -> None:
    assert parse_hours(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "abc", "-1", "0.1", "24.5", "999", "8h"],
)
def test_parse_hours_rejects_invalid(raw: str) -> None:
    assert parse_hours(raw) is None


def test_parse_hours_boundaries() -> None:
    assert parse_hours(str(MIN_WORK_HOURS)) == MIN_WORK_HOURS
    assert parse_hours(str(MAX_HOURS)) == MAX_HOURS


def test_parse_hours_accepts_zero_as_day_off() -> None:
    assert parse_hours("0") == DAY_OFF
    assert parse_hours("0.0") == DAY_OFF
    assert parse_hours(" 0 ") == DAY_OFF


def test_is_day_off_helper() -> None:
    assert is_day_off(DAY_OFF) is True
    assert is_day_off(Decimal("0")) is True
    assert is_day_off(Decimal("0.00")) is True
    assert is_day_off(Decimal("8")) is False
    assert is_day_off(Decimal("0.25")) is False


# ---- smart_suggest ---------------------------------------------------------


def test_smart_suggest_empty_returns_none() -> None:
    assert smart_suggest([]) is None


def test_smart_suggest_returns_modal_when_habitual() -> None:
    entries = [_entry("8", i) for i in range(SUGGEST_MIN_OCCURRENCES)]
    entries.append(_entry("6", SUGGEST_MIN_OCCURRENCES))
    assert smart_suggest(entries) == Decimal("8")


def test_smart_suggest_returns_none_when_not_habitual() -> None:
    # Three different values across 5 days — no clear winner.
    entries = [
        _entry("8", 0),
        _entry("9", 1),
        _entry("10", 2),
        _entry("9", 3),
        _entry("8", 4),
    ]
    assert smart_suggest(entries) is None


def test_smart_suggest_uses_only_window() -> None:
    # Older "12" entries dominate but the window only covers the most recent 5.
    entries = [_entry("8", i) for i in range(SUGGEST_WINDOW_DAYS)]
    entries.extend(_entry("12", i) for i in range(SUGGEST_WINDOW_DAYS, 15))
    assert smart_suggest(entries) == Decimal("8")


# ---- quick_pick_values -----------------------------------------------------


def test_quick_pick_without_suggestion() -> None:
    assert quick_pick_values(None) == list(QUICK_HOURS)


def test_quick_pick_with_existing_suggestion_dedupes() -> None:
    picks = quick_pick_values(Decimal("8"))
    assert picks[0] == Decimal("8")
    assert picks.count(Decimal("8")) == 1


def test_quick_pick_with_novel_suggestion_prepends() -> None:
    picks = quick_pick_values(Decimal("11"))
    assert picks[0] == Decimal("11")
    assert len(picks) == len(QUICK_HOURS) + 1


# ---- personalized_picks ----------------------------------------------------


def test_personalized_picks_empty_history_falls_back_to_defaults() -> None:
    assert personalized_picks([]) == list(QUICK_HOURS)


def test_personalized_picks_with_suggested_first() -> None:
    picks = personalized_picks([], Decimal("11"))
    assert picks[0] == Decimal("11")


def test_personalized_picks_promotes_recent_unique_values() -> None:
    entries = [
        _entry("11", 0),
        _entry("11", 1),  # duplicate — dropped
        _entry("13", 2),
        _entry("0", 3),  # day-off — skipped
        _entry("9", 4),
    ]
    picks = personalized_picks(entries, max_items=4)
    # Recent unique values first (newest-first), then defaults fill in.
    assert picks[0] == Decimal("11")
    assert picks[1] == Decimal("13")
    assert picks[2] == Decimal("9")
    assert len(picks) == 4


def test_personalized_picks_dedupes_against_suggested() -> None:
    entries = [_entry("8", 0), _entry("9", 1)]
    picks = personalized_picks(entries, Decimal("8"))
    assert picks.count(Decimal("8")) == 1
    assert picks[0] == Decimal("8")


def test_personalized_picks_respects_max_items() -> None:
    entries = [_entry("11", 0), _entry("13", 1), _entry("9", 2)]
    picks = personalized_picks(entries, Decimal("8"), max_items=3)
    assert picks == [Decimal("8"), Decimal("11"), Decimal("13")]


def test_personalized_picks_skips_day_off_values() -> None:
    entries = [_entry("0", 0), _entry("0", 1)]
    picks = personalized_picks(entries)
    assert all(v > 0 for v in picks)
    assert picks == list(QUICK_HOURS)


# ---- format_hours ----------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("8"), "8"),
        (Decimal("8.00"), "8"),
        (Decimal("8.50"), "8.5"),
        (Decimal("0.25"), "0.25"),
        (Decimal("10"), "10"),
    ],
)
def test_format_hours(value: Decimal, expected: str) -> None:
    assert format_hours(value) == expected
