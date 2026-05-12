"""Phase 7.2: tests for smart-reminder helpers."""

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
from src.core.models import Advance, Crew, DayEntry, SalaryPayment, User
from src.services import accounting as accounting_module
from src.services.advances import SalaryBreakdown
from src.services.reminders_smart import (
    _business_days_between,
    aged_open_periods,
    users_with_gap,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES_FOR_TESTS = [
    Crew.__table__,
    User.__table__,
    DayEntry.__table__,
    Advance.__table__,
    SalaryPayment.__table__,
]

_TZ = ZoneInfo("Europe/Warsaw")


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        for table in _TABLES_FOR_TESTS:
            await conn.run_sync(table.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_user(s: AsyncSession, *, created: date) -> User:
    u = User(
        tg_id=111,
        name="Иван",
        locale="ru",
        currency="PLN",
        role="worker",
        hourly_rate=Decimal("30.00"),
        created_at=datetime(created.year, created.month, created.day, tzinfo=UTC),
    )
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


# --- _business_days_between ------------------------------------------


def test_business_days_between_full_week() -> None:
    # Mon→Fri = 5 weekdays after a Sun start.
    assert _business_days_between(date(2026, 5, 3), date(2026, 5, 8)) == 5


def test_business_days_between_skips_weekend() -> None:
    # Fri exclusive → Mon inclusive = 1 weekday (Monday only).
    assert _business_days_between(date(2026, 5, 8), date(2026, 5, 11)) == 1


def test_business_days_between_zero_for_reversed_range() -> None:
    assert _business_days_between(date(2026, 5, 10), date(2026, 5, 10)) == 0
    assert _business_days_between(date(2026, 5, 11), date(2026, 5, 10)) == 0


# --- users_with_gap --------------------------------------------------


@pytest.mark.asyncio
async def test_no_gap_when_recent_entry(session: AsyncSession) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    session.add(
        DayEntry(user_id=u.id, day=date(2026, 5, 11), hours=Decimal("8")),
    )
    await session.commit()
    gaps = await users_with_gap(session, today=date(2026, 5, 12))
    assert gaps == []


@pytest.mark.asyncio
async def test_gap_detected_after_three_weekdays(session: AsyncSession) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    # Last entry on Mon May 4, "today" is Thu May 7 → 3 weekdays gap.
    session.add(
        DayEntry(user_id=u.id, day=date(2026, 5, 4), hours=Decimal("8")),
    )
    await session.commit()
    gaps = await users_with_gap(session, today=date(2026, 5, 7))
    assert len(gaps) == 1
    assert gaps[0].user.id == u.id
    assert gaps[0].last_day == date(2026, 5, 4)
    assert gaps[0].gap_business_days == 3


@pytest.mark.asyncio
async def test_weekend_only_gap_is_ignored(session: AsyncSession) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    # Last entry Fri May 8; "today" is Sun May 10 → 0 weekdays between.
    session.add(
        DayEntry(user_id=u.id, day=date(2026, 5, 8), hours=Decimal("8")),
    )
    await session.commit()
    gaps = await users_with_gap(session, today=date(2026, 5, 10))
    assert gaps == []


@pytest.mark.asyncio
async def test_new_user_no_nudge_too_early(session: AsyncSession) -> None:
    # Created today, no entries → don't nudge.
    await _seed_user(session, created=date(2026, 5, 12))
    gaps = await users_with_gap(session, today=date(2026, 5, 12))
    assert gaps == []


@pytest.mark.asyncio
async def test_old_user_no_entries_is_nudged(session: AsyncSession) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    gaps = await users_with_gap(session, today=date(2026, 5, 12))
    assert len(gaps) == 1
    assert gaps[0].user.id == u.id
    assert gaps[0].last_day is None
    assert gaps[0].gap_business_days >= 3


# --- aged_open_periods -----------------------------------------------


def _stub_compute_salary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    by_month: dict[tuple[int, int], tuple[Decimal, Decimal | None]],
) -> None:
    """Replace compute_salary with a per-(year, month) lookup table."""
    async def fake(
        _session: AsyncSession, *, user: User, year: int, month: int,
        tz: ZoneInfo,  # noqa: ARG001
    ) -> SalaryBreakdown:
        hours, earnings = by_month.get((year, month), (Decimal(0), None))
        return SalaryBreakdown(
            user_id=user.id,
            year=year, month=month,
            day_entries_hours=hours,
            day_entries_earnings=earnings,
            shifts_hours=Decimal(0),
            shifts_earnings=None,
            advances_total=Decimal(0),
            net_payable=earnings,
        )
    monkeypatch.setattr(accounting_module, "compute_salary", fake)


@pytest.mark.asyncio
async def test_aged_open_periods_returns_empty_when_no_open(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    _stub_compute_salary(monkeypatch, by_month={})
    aged = await aged_open_periods(
        session, user=u, tz=_TZ, today=date(2026, 5, 12),
    )
    assert aged == []


@pytest.mark.asyncio
async def test_aged_open_periods_includes_old_unpaid(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    # March 2026 has 8h @ 30 PLN = 240 unpaid.
    _stub_compute_salary(
        monkeypatch,
        by_month={(2026, 3): (Decimal("8"), Decimal("240.00"))},
    )
    # Today = May 12, 2026 → March 2026 ended Mar 31 → age = 42 days ≥ 30.
    aged = await aged_open_periods(
        session, user=u, tz=_TZ, today=date(2026, 5, 12),
    )
    assert len(aged) == 1
    assert aged[0].year == 2026
    assert aged[0].month == 3


@pytest.mark.asyncio
async def test_aged_open_periods_excludes_recent_period(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    u = await _seed_user(session, created=date(2025, 1, 1))
    # April 2026 owed, ended Apr 30. Today = May 12 → age = 12 days < 30.
    _stub_compute_salary(
        monkeypatch,
        by_month={(2026, 4): (Decimal("8"), Decimal("240.00"))},
    )
    aged = await aged_open_periods(
        session, user=u, tz=_TZ, today=date(2026, 5, 12),
    )
    assert aged == []
