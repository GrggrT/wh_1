"""Pure-logic tests for the Phase 5.2 advances service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest
from src.services.advances import (
    compute_day_entry_earnings,
    month_bounds,
    parse_amount,
    parse_year_month,
)


@dataclass
class FakeSite:
    id: int
    hourly_rate: Decimal | None


@dataclass
class FakeDayEntry:
    user_id: int
    day: date
    hours: Decimal
    site_id: int | None = None


# ---- parse_amount ----------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("100", Decimal("100.00")),
        ("100.50", Decimal("100.50")),
        ("100,50", Decimal("100.50")),
        ("  250  ", Decimal("250.00")),
    ],
)
def test_parse_amount_valid(raw: str, expected: Decimal) -> None:
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("raw", ["", "abc", "0", "-1", "-100", "1000001", "5e2"])
def test_parse_amount_invalid(raw: str) -> None:
    assert parse_amount(raw) is None


# ---- parse_year_month ------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2026-05", (2026, 5)), ("2000-01", (2000, 1)), ("2100-12", (2100, 12))],
)
def test_parse_year_month_valid(raw: str, expected: tuple[int, int]) -> None:
    assert parse_year_month(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "2026", "2026-13", "2026-00", "1999-05", "2101-05", "abc-de", "2026/05"],
)
def test_parse_year_month_invalid(raw: str) -> None:
    assert parse_year_month(raw) is None


# ---- month_bounds ----------------------------------------------------------


def test_month_bounds_typical_month() -> None:
    first, last = month_bounds(2026, 5)
    assert first == date(2026, 5, 1)
    assert last == date(2026, 5, 31)


def test_month_bounds_february_leap() -> None:
    first, last = month_bounds(2024, 2)
    assert first == date(2024, 2, 1)
    assert last == date(2024, 2, 29)


def test_month_bounds_december() -> None:
    first, last = month_bounds(2026, 12)
    assert first == date(2026, 12, 1)
    assert last == date(2026, 12, 31)


# ---- compute_day_entry_earnings -------------------------------------------


def test_earnings_uses_user_rate_when_no_site() -> None:
    entries = [
        FakeDayEntry(user_id=1, day=date(2026, 5, 1), hours=Decimal("8")),
        FakeDayEntry(user_id=1, day=date(2026, 5, 2), hours=Decimal("4")),
    ]
    hours, earnings = compute_day_entry_earnings(
        entries, sites_by_id={}, user_rate=Decimal("50"),
    )
    assert hours == Decimal("12.00")
    assert earnings == Decimal("600.00")


def test_earnings_prefers_site_rate_over_user_rate() -> None:
    sites = {7: FakeSite(id=7, hourly_rate=Decimal("80"))}
    entries = [
        FakeDayEntry(user_id=1, day=date(2026, 5, 1), hours=Decimal("8"), site_id=7),
    ]
    hours, earnings = compute_day_entry_earnings(
        entries, sites_by_id=sites, user_rate=Decimal("50"),
    )
    assert hours == Decimal("8.00")
    assert earnings == Decimal("640.00")


def test_earnings_falls_back_to_user_rate_when_site_has_no_rate() -> None:
    sites = {7: FakeSite(id=7, hourly_rate=None)}
    entries = [
        FakeDayEntry(user_id=1, day=date(2026, 5, 1), hours=Decimal("8"), site_id=7),
    ]
    _hours, earnings = compute_day_entry_earnings(
        entries, sites_by_id=sites, user_rate=Decimal("50"),
    )
    assert earnings == Decimal("400.00")


def test_earnings_none_when_no_rate_anywhere() -> None:
    entries = [
        FakeDayEntry(user_id=1, day=date(2026, 5, 1), hours=Decimal("8")),
    ]
    hours, earnings = compute_day_entry_earnings(
        entries, sites_by_id={}, user_rate=None,
    )
    assert hours == Decimal("8.00")
    assert earnings is None


def test_earnings_mixed_priced_and_unpriced_keeps_only_priced() -> None:
    # Two entries: one with a site rate, one without (no user_rate either).
    sites = {7: FakeSite(id=7, hourly_rate=Decimal("100"))}
    entries = [
        FakeDayEntry(user_id=1, day=date(2026, 5, 1), hours=Decimal("8"), site_id=7),
        FakeDayEntry(user_id=1, day=date(2026, 5, 2), hours=Decimal("4")),
    ]
    hours, earnings = compute_day_entry_earnings(
        entries, sites_by_id=sites, user_rate=None,
    )
    # Hours always sum; earnings only counts priced ones.
    assert hours == Decimal("12.00")
    assert earnings == Decimal("800.00")
