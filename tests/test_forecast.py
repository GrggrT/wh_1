"""Phase 7.4: forecast service tests."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.core.models import DayEntry, User
from src.services import forecast as forecast_module
from src.services.advances import SalaryBreakdown
from src.services.forecast import (
    _business_days_elapsed,
    _business_days_in_month,
    compute_forecast,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TZ = ZoneInfo("Europe/Warsaw")


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)  # type: ignore[attr-defined]
        await conn.run_sync(DayEntry.__table__.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_user(s: AsyncSession) -> User:
    u = User(
        tg_id=111, name="Иван", locale="ru",
        currency="PLN", role="worker", hourly_rate=Decimal("30.00"),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


def _stub_salary(
    monkeypatch: pytest.MonkeyPatch, *,
    hours: Decimal, earnings: Decimal | None,
) -> None:
    async def fake(
        _s: AsyncSession, *, user: User, year: int, month: int,
        tz: ZoneInfo,  # noqa: ARG001
    ) -> SalaryBreakdown:
        return SalaryBreakdown(
            user_id=user.id, year=year, month=month,
            day_entries_hours=hours, day_entries_earnings=earnings,
            shifts_hours=Decimal(0), shifts_earnings=None,
            advances_total=Decimal(0),
            net_payable=earnings,
        )
    monkeypatch.setattr(forecast_module, "compute_salary", fake)


# --- business-day math ------------------------------------------------


def test_business_days_in_month_counts_mon_fri() -> None:
    # May 2026: 21 weekdays.
    assert _business_days_in_month(2026, 5) == 21


def test_business_days_elapsed_includes_today() -> None:
    # Tue May 12 2026 → business days 1-12: Fri 1, Mon-Fri 4-8, Mon-Tue 11-12 = 8.
    assert _business_days_elapsed(2026, 5, date(2026, 5, 12)) == 8


def test_business_days_elapsed_past_month_returns_total() -> None:
    assert _business_days_elapsed(2026, 4, date(2026, 5, 1)) == 22


def test_business_days_elapsed_future_month_returns_zero() -> None:
    assert _business_days_elapsed(2026, 6, date(2026, 5, 1)) == 0


# --- compute_forecast -------------------------------------------------


@pytest.mark.asyncio
async def test_forecast_projects_linearly_from_pace(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    # 32 h MTD over 8 elapsed business days → 4 h/bd. 13 remaining → +52 h.
    _stub_salary(
        monkeypatch, hours=Decimal("32"), earnings=Decimal("960.00"),
    )
    fc = await compute_forecast(
        session, user=user, year=2026, month=5,
        today=date(2026, 5, 12), tz=_TZ,
    )
    assert fc.business_days_elapsed == 8
    assert fc.business_days_total == 21
    assert fc.business_days_remaining == 13
    assert fc.projected_total_hours == Decimal("84.00")
    # 84 h * (960/32 = 30 PLN/h) = 2520 PLN.
    assert fc.projected_total_earnings == Decimal("2520.00")


@pytest.mark.asyncio
async def test_forecast_no_projection_when_zero_business_days_elapsed(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_salary(monkeypatch, hours=Decimal(0), earnings=None)
    # June 2026 starts on Mon. today = May 31 (Sun) → 0 business days in June elapsed.
    fc = await compute_forecast(
        session, user=user, year=2026, month=6,
        today=date(2026, 5, 31), tz=_TZ,
    )
    assert fc.business_days_elapsed == 0
    assert fc.projected_total_hours is None
    assert fc.projected_total_earnings is None


@pytest.mark.asyncio
async def test_forecast_past_month_returns_actuals(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_salary(
        monkeypatch, hours=Decimal("160"), earnings=Decimal("4800.00"),
    )
    fc = await compute_forecast(
        session, user=user, year=2026, month=4,
        today=date(2026, 5, 12), tz=_TZ,
    )
    # Past month: remaining=0 → projected = MTD actuals.
    assert fc.business_days_remaining == 0
    assert fc.projected_total_hours == Decimal("160")
    assert fc.projected_total_earnings == Decimal("4800.00")


@pytest.mark.asyncio
async def test_forecast_unpriced_hours_keeps_projection_for_hours_only(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_salary(monkeypatch, hours=Decimal("32"), earnings=None)
    fc = await compute_forecast(
        session, user=user, year=2026, month=5,
        today=date(2026, 5, 12), tz=_TZ,
    )
    assert fc.projected_total_hours == Decimal("84.00")
    assert fc.projected_total_earnings is None
