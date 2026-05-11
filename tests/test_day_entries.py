"""Tests for the Phase 5.1 day-entries service (pure logic; no DB)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

import pytest
from src.services.day_entries import (
    MAX_HOURS,
    MIN_HOURS,
    QUICK_HOURS,
    SUGGEST_MIN_OCCURRENCES,
    SUGGEST_WINDOW_DAYS,
    format_hours,
    parse_hours,
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
    ["", "abc", "-1", "0", "0.1", "24.5", "999", "8h"],
)
def test_parse_hours_rejects_invalid(raw: str) -> None:
    assert parse_hours(raw) is None


def test_parse_hours_boundaries() -> None:
    assert parse_hours(str(MIN_HOURS)) == MIN_HOURS
    assert parse_hours(str(MAX_HOURS)) == MAX_HOURS


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
