"""Tests for shift-related business logic (no DB required)."""

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.services.reports import compute_hours, compute_period_hours, split_shift_at_midnight

from tests.conftest import FakeShift


class TestComputeHours:
    def test_simple_8_hours(self) -> None:
        start = datetime(2026, 5, 8, 8, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        end = datetime(2026, 5, 8, 16, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        assert compute_hours(start, end) == Decimal(8)

    def test_partial_hour(self) -> None:
        start = datetime(2026, 5, 8, 8, 0, tzinfo=ZoneInfo("Europe/Warsaw"))
        end = datetime(2026, 5, 8, 8, 30, tzinfo=ZoneInfo("Europe/Warsaw"))
        assert compute_hours(start, end) == Decimal("0.5")

    def test_cross_midnight(self) -> None:
        tz = ZoneInfo("Europe/Warsaw")
        start = datetime(2026, 5, 8, 23, 30, tzinfo=tz)
        end = datetime(2026, 5, 9, 0, 30, tzinfo=tz)
        assert compute_hours(start, end) == Decimal(1)

    def test_dst_spring_forward(self) -> None:
        """Europe/Warsaw spring forward: 2026-03-29 02:00 -> 03:00.
        Use UTC timestamps to ensure correct elapsed time across DST."""
        utc = ZoneInfo("UTC")
        # 2026-03-29 01:00 CET = 00:00 UTC (CET = UTC+1)
        start = datetime(2026, 3, 29, 0, 0, tzinfo=utc)
        # 2026-03-29 04:00 CEST = 02:00 UTC (CEST = UTC+2)
        end = datetime(2026, 3, 29, 2, 0, tzinfo=utc)
        # Actual elapsed: 2 hours
        hours = compute_hours(start, end)
        assert hours == Decimal(2)

    def test_dst_fall_back(self) -> None:
        """Europe/Warsaw fall back: 2026-10-25 03:00 -> 02:00.
        Use UTC timestamps to ensure correct elapsed time across DST."""
        utc = ZoneInfo("UTC")
        # 2026-10-25 01:00 CEST = 23:00 Oct 24 UTC (CEST = UTC+2)
        start = datetime(2026, 10, 24, 23, 0, tzinfo=utc)
        # 2026-10-25 04:00 CET = 03:00 UTC (CET = UTC+1)
        end = datetime(2026, 10, 25, 3, 0, tzinfo=utc)
        # Actual elapsed: 4 hours
        hours = compute_hours(start, end)
        assert hours == Decimal(4)


class TestSplitShiftAtMidnight:
    def test_no_split_same_day(self) -> None:
        tz = ZoneInfo("Europe/Warsaw")
        start = datetime(2026, 5, 8, 8, 0, tzinfo=tz)
        end = datetime(2026, 5, 8, 16, 0, tzinfo=tz)
        segments = split_shift_at_midnight(start, end, tz)
        assert len(segments) == 1
        assert segments[0] == (start, end)

    def test_split_cross_midnight(self) -> None:
        tz = ZoneInfo("Europe/Warsaw")
        start = datetime(2026, 5, 8, 23, 30, tzinfo=tz)
        end = datetime(2026, 5, 9, 0, 30, tzinfo=tz)
        segments = split_shift_at_midnight(start, end, tz)
        assert len(segments) == 2
        assert segments[0][0] == start
        assert segments[0][1].hour == 0 and segments[0][1].minute == 0
        assert segments[1][1] == end

    def test_split_multi_day(self) -> None:
        tz = ZoneInfo("Europe/Warsaw")
        start = datetime(2026, 5, 8, 22, 0, tzinfo=tz)
        end = datetime(2026, 5, 10, 2, 0, tzinfo=tz)
        segments = split_shift_at_midnight(start, end, tz)
        assert len(segments) == 3


class TestCrewAggregation:
    def test_per_user_split(self) -> None:
        """compute_period_hours called per-user yields independent totals."""
        tz = ZoneInfo("Europe/Warsaw")
        u1 = FakeShift(
            id=1, user_id=10, site_id=None,
            start_at=datetime(2026, 5, 8, 8, 0, tzinfo=tz),
            end_at=datetime(2026, 5, 8, 16, 0, tzinfo=tz),
        )
        u2_a = FakeShift(
            id=2, user_id=20, site_id=None,
            start_at=datetime(2026, 5, 8, 9, 0, tzinfo=tz),
            end_at=datetime(2026, 5, 8, 13, 0, tzinfo=tz),
        )
        u2_b = FakeShift(
            id=3, user_id=20, site_id=None,
            start_at=datetime(2026, 5, 8, 14, 0, tzinfo=tz),
            end_at=datetime(2026, 5, 8, 17, 0, tzinfo=tz),
        )
        d = date(2026, 5, 8)
        u1_hours = compute_period_hours([u1], d, d, tz)  # type: ignore[arg-type]
        u2_hours = compute_period_hours([u2_a, u2_b], d, d, tz)  # type: ignore[arg-type]
        assert u1_hours == Decimal("8.00")
        assert u2_hours == Decimal("7.00")
        assert (u1_hours + u2_hours) == Decimal("15.00")


class TestComputePeriodHours:
    def test_timezone_correctness(self) -> None:
        """Spec check #3: shift crossing midnight, each day gets correct portion."""
        tz = ZoneInfo("Europe/Warsaw")

        shift = FakeShift(
            id=1,
            site_id=None,
            start_at=datetime(2026, 5, 8, 23, 30, tzinfo=tz),
            end_at=datetime(2026, 5, 9, 0, 30, tzinfo=tz),
        )

        hours_may8 = compute_period_hours([shift], date(2026, 5, 8), date(2026, 5, 8), tz)  # type: ignore[arg-type]
        assert hours_may8 == Decimal("0.50")

        hours_may9 = compute_period_hours([shift], date(2026, 5, 9), date(2026, 5, 9), tz)  # type: ignore[arg-type]
        assert hours_may9 == Decimal("0.50")

        hours_both = compute_period_hours([shift], date(2026, 5, 8), date(2026, 5, 9), tz)  # type: ignore[arg-type]
        assert hours_both == Decimal("1.00")
