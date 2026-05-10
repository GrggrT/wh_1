"""Tests for compute_period_earnings: site rate vs user rate fallback."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from src.services.reports import compute_period_earnings

from tests.conftest import FakeShift, FakeSite

_TZ = ZoneInfo("Europe/Warsaw")


def _shift(
    sid: int, site_id: int | None, start: datetime, end: datetime,
) -> FakeShift:
    return FakeShift(id=sid, site_id=site_id, start_at=start, end_at=end)


def test_uses_site_rate_when_present() -> None:
    s_start = datetime(2026, 5, 8, 8, 0, tzinfo=_TZ)
    s_end = datetime(2026, 5, 8, 16, 0, tzinfo=_TZ)
    sh = _shift(1, 10, s_start, s_end)
    site = FakeSite(id=10, hourly_rate=Decimal("60.00"))
    target = date(2026, 5, 8)
    amount = compute_period_earnings(
        [sh],  # type: ignore[arg-type]
        target, target, _TZ,
        {10: site},  # type: ignore[dict-item]
        Decimal("40.00"),  # user rate (should be ignored)
    )
    assert amount == Decimal("480.00")  # 8h * 60 zł


def test_falls_back_to_user_rate_when_site_has_none() -> None:
    s_start = datetime(2026, 5, 8, 8, 0, tzinfo=_TZ)
    s_end = datetime(2026, 5, 8, 12, 0, tzinfo=_TZ)
    sh = _shift(1, 10, s_start, s_end)
    site = FakeSite(id=10, hourly_rate=None)
    target = date(2026, 5, 8)
    amount = compute_period_earnings(
        [sh],  # type: ignore[arg-type]
        target, target, _TZ,
        {10: site},  # type: ignore[dict-item]
        Decimal("40.00"),
    )
    assert amount == Decimal("160.00")  # 4h * 40 zł


def test_returns_none_when_no_rates_anywhere() -> None:
    s_start = datetime(2026, 5, 8, 8, 0, tzinfo=_TZ)
    s_end = datetime(2026, 5, 8, 12, 0, tzinfo=_TZ)
    sh = _shift(1, None, s_start, s_end)
    target = date(2026, 5, 8)
    amount = compute_period_earnings(
        [sh],  # type: ignore[arg-type]
        target, target, _TZ,
        {},
        None,
    )
    assert amount is None


def test_skips_unpriced_shifts_but_returns_priced_ones() -> None:
    base = datetime(2026, 5, 8, 8, 0, tzinfo=_TZ)
    sh_priced = _shift(1, 10, base, base + timedelta(hours=2))
    sh_unpriced = _shift(2, None, base + timedelta(hours=4), base + timedelta(hours=6))
    site = FakeSite(id=10, hourly_rate=Decimal("50.00"))
    target = date(2026, 5, 8)
    amount = compute_period_earnings(
        [sh_priced, sh_unpriced],  # type: ignore[arg-type]
        target, target, _TZ,
        {10: site},  # type: ignore[dict-item]
        None,  # no user rate, so unpriced shift is skipped
    )
    assert amount == Decimal("100.00")
