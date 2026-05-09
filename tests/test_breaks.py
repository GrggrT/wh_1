"""Tests for break service: total_break_hours window clipping."""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.services.breaks import total_break_hours

_UTC = ZoneInfo("UTC")


@dataclass
class FakeBreak:
    shift_id: int = 1
    start_at: datetime = field(default_factory=lambda: datetime(2026, 5, 8, 12, 0, tzinfo=_UTC))
    end_at: datetime | None = None


def test_no_breaks_returns_zero() -> None:
    assert total_break_hours([]) == Decimal(0)


def test_open_break_skipped() -> None:
    b = FakeBreak(end_at=None)
    assert total_break_hours([b]) == Decimal(0)  # type: ignore[list-item]


def test_full_30_minute_break() -> None:
    start = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)
    b = FakeBreak(start_at=start, end_at=start + timedelta(minutes=30))
    total = total_break_hours([b])  # type: ignore[list-item]
    assert total == Decimal("1800") / Decimal("3600")  # 0.5 hour


def test_two_breaks_summed() -> None:
    base = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)
    b1 = FakeBreak(start_at=base, end_at=base + timedelta(minutes=30))
    b2 = FakeBreak(
        start_at=base + timedelta(hours=2),
        end_at=base + timedelta(hours=2, minutes=15),
    )
    total = total_break_hours([b1, b2])  # type: ignore[list-item]
    expected = (Decimal(30 * 60) + Decimal(15 * 60)) / Decimal("3600")
    assert total == expected


def test_break_clipped_to_window() -> None:
    base = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)
    b = FakeBreak(start_at=base, end_at=base + timedelta(hours=1))
    window_start = base + timedelta(minutes=30)
    window_end = base + timedelta(hours=2)
    total = total_break_hours([b], window_start, window_end)  # type: ignore[list-item]
    # Only the second 30 minutes of the break fall inside the window.
    assert total == Decimal(30 * 60) / Decimal("3600")


def test_break_outside_window_excluded() -> None:
    base = datetime(2026, 5, 8, 12, 0, tzinfo=_UTC)
    b = FakeBreak(start_at=base, end_at=base + timedelta(minutes=15))
    window_start = base + timedelta(hours=1)
    window_end = base + timedelta(hours=2)
    assert total_break_hours([b], window_start, window_end) == Decimal(0)  # type: ignore[list-item]


def test_compute_period_hours_subtracts_breaks() -> None:
    from datetime import date

    from src.services.reports import compute_period_hours

    from tests.conftest import FakeShift

    tz = ZoneInfo("Europe/Warsaw")
    shift_start = datetime(2026, 5, 8, 8, 0, tzinfo=tz)
    shift_end = datetime(2026, 5, 8, 16, 0, tzinfo=tz)
    shift = FakeShift(id=42, start_at=shift_start, end_at=shift_end)
    # 30-min break inside the shift
    b = FakeBreak(
        shift_id=42,
        start_at=shift_start + timedelta(hours=4),
        end_at=shift_start + timedelta(hours=4, minutes=30),
    )
    breaks_by_shift = {42: [b]}
    target = date(2026, 5, 8)
    gross = compute_period_hours([shift], target, target, tz)  # type: ignore[arg-type]
    net = compute_period_hours(
        [shift], target, target, tz, breaks_by_shift,  # type: ignore[arg-type]
    )
    assert gross == Decimal("8.00")
    assert net == Decimal("7.50")
