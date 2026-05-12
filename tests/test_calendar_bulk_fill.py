"""Phase 7.3: bulk-fill workweek button on the inline calendar."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.bot.handlers.calendar import _bulk_fill_workweek
from src.core.models import DayEntry, User


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


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
    )
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


@pytest.mark.asyncio
async def test_bulk_fill_creates_only_weekday_entries(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    # May 2026: 1st = Fri, 2-3 weekend, 4-8 weekdays, etc.
    today = date(2026, 5, 31)
    created = await _bulk_fill_workweek(
        session, user_id=user.id, year=2026, month=5, today=today,
    )
    await session.commit()

    # May 2026 has exactly 21 weekdays.
    assert created == 21
    days = (
        await session.execute(
            select(DayEntry.day, DayEntry.hours).where(
                DayEntry.user_id == user.id,
            ),
        )
    ).all()
    assert len(days) == 21
    for d, hours in days:
        assert d.weekday() < 5
        assert hours == Decimal("10")


@pytest.mark.asyncio
async def test_bulk_fill_caps_at_today(session: AsyncSession) -> None:
    user = await _seed_user(session)
    # today = Tue May 12 2026 → eligible weekdays in May 1..12 = 1, 4-8, 11, 12 = 8 days.
    created = await _bulk_fill_workweek(
        session, user_id=user.id, year=2026, month=5, today=date(2026, 5, 12),
    )
    await session.commit()
    assert created == 8


@pytest.mark.asyncio
async def test_bulk_fill_skips_existing_entries(session: AsyncSession) -> None:
    user = await _seed_user(session)
    # Pre-record a day-off on Mon May 11 and custom hours on Tue May 5.
    session.add(DayEntry(user_id=user.id, day=date(2026, 5, 11), hours=Decimal("0")))
    session.add(DayEntry(user_id=user.id, day=date(2026, 5, 5), hours=Decimal("10")))
    await session.commit()

    created = await _bulk_fill_workweek(
        session, user_id=user.id, year=2026, month=5, today=date(2026, 5, 31),
    )
    await session.commit()
    assert created == 19  # 21 weekdays − 2 pre-existing.

    # Pre-existing rows must be untouched.
    rows = dict(
        (
            await session.execute(
                select(DayEntry.day, DayEntry.hours).where(
                    DayEntry.user_id == user.id,
                ),
            )
        ).all(),
    )
    assert rows[date(2026, 5, 11)] == Decimal("0")
    assert rows[date(2026, 5, 5)] == Decimal("10")


@pytest.mark.asyncio
async def test_bulk_fill_future_month_is_noop(session: AsyncSession) -> None:
    user = await _seed_user(session)
    # today is in April but we try to bulk-fill May.
    created = await _bulk_fill_workweek(
        session, user_id=user.id, year=2026, month=5, today=date(2026, 4, 1),
    )
    await session.commit()
    assert created == 0
