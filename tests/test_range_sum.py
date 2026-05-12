"""Tests for the /range hours + earnings range-sum service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.core.models import Crew, DayEntry, User
from src.services.day_entries import DAY_OFF
from src.services.range_sum import compute_range_sum, parse_iso_date


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES = [Crew.__table__, User.__table__, DayEntry.__table__]


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        for table in _TABLES:
            await conn.run_sync(table.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _seed_user(
    session: AsyncSession,
    *,
    rate: Decimal | None = Decimal("50.00"),
) -> User:
    user = User(tg_id=100, name="W", hourly_rate=rate, currency="PLN")
    session.add(user)
    await session.flush()
    return user


def test_parse_iso_date_accepts_valid() -> None:
    assert parse_iso_date("2026-05-01") == date(2026, 5, 1)
    assert parse_iso_date("  2026-05-01  ") == date(2026, 5, 1)


def test_parse_iso_date_rejects_garbage() -> None:
    assert parse_iso_date("05/01/2026") is None
    assert parse_iso_date("not a date") is None
    assert parse_iso_date("") is None


async def test_range_sum_sums_inclusive_endpoints(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    for d, h in [
        (date(2026, 5, 1), Decimal("8.00")),
        (date(2026, 5, 2), Decimal("4.50")),
        (date(2026, 5, 3), Decimal("8.00")),  # outside upper bound
    ]:
        session.add(DayEntry(user_id=user.id, day=d, hours=h, note=None))
    await session.flush()

    rs = await compute_range_sum(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 2),
    )
    assert rs.total_hours == Decimal("12.50")
    assert rs.days_with_hours == 2
    assert rs.total_earnings == Decimal("625.00")


async def test_range_sum_skips_day_off_rows(session: AsyncSession) -> None:
    user = await _seed_user(session)
    session.add(DayEntry(
        user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    ))
    session.add(DayEntry(
        user_id=user.id, day=date(2026, 5, 2),
        hours=DAY_OFF, note=None,
    ))
    await session.flush()

    rs = await compute_range_sum(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 3),
    )
    assert rs.total_hours == Decimal("8.00")
    assert rs.days_with_hours == 1


async def test_range_sum_returns_none_earnings_without_rate(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session, rate=None)
    session.add(DayEntry(
        user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    ))
    await session.flush()

    rs = await compute_range_sum(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 1),
    )
    assert rs.total_hours == Decimal("8.00")
    assert rs.total_earnings is None


async def test_range_sum_empty_window_is_zero(session: AsyncSession) -> None:
    user = await _seed_user(session)
    rs = await compute_range_sum(
        session, user=user, start=date(2026, 1, 1), end=date(2026, 1, 31),
    )
    assert rs.total_hours == Decimal("0.00")
    assert rs.days_with_hours == 0
    assert rs.total_earnings == Decimal("0.00")
