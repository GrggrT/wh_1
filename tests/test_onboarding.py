"""Phase 6.3: onboarding service tests.

Service-layer coverage for the first-run wizard. We reuse the
in-memory aiosqlite engine pattern from ``test_db_integration``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.core.models import Crew, User
from src.services.onboarding import (
    complete_onboarding,
    is_onboarded,
    parse_rate,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES_FOR_TESTS = [Crew.__table__, User.__table__]


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


async def _seed_user(session: AsyncSession) -> User:
    user = User(tg_id=42, name="Old Name")
    session.add(user)
    await session.flush()
    return user


def test_parse_rate_accepts_valid_amounts() -> None:
    assert parse_rate("50") == Decimal("50")
    assert parse_rate("50,25") == Decimal("50.25")
    assert parse_rate("  75.00  ") == Decimal("75.00")


def test_parse_rate_rejects_garbage() -> None:
    assert parse_rate("hello") is None
    assert parse_rate("") is None
    assert parse_rate("-5") is None


async def test_is_onboarded_reflects_column(session: AsyncSession) -> None:
    user = await _seed_user(session)
    assert is_onboarded(user) is False
    await complete_onboarding(
        session,
        user_id=user.id,
        name="New Name",
        hourly_rate=None,
        remind_hour_local=None,
    )
    assert is_onboarded(user) is True


async def test_complete_onboarding_writes_all_fields(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    user.day_reminder_last_sent = None
    updated = await complete_onboarding(
        session,
        user_id=user.id,
        name="Alice",
        hourly_rate=Decimal("80.00"),
        remind_hour_local=20,
    )
    assert updated.name == "Alice"
    assert updated.hourly_rate == Decimal("80.00")
    assert updated.remind_hour_local == 20
    assert updated.onboarded_at is not None


async def test_complete_onboarding_persists_currency(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    assert user.currency == "PLN"  # server default
    updated = await complete_onboarding(
        session,
        user_id=user.id,
        name="Alice",
        hourly_rate=Decimal("35.00"),
        remind_hour_local=None,
        currency="USD",
    )
    assert updated.currency == "USD"


async def test_complete_onboarding_truncates_long_name(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    long_name = "x" * 200
    updated = await complete_onboarding(
        session,
        user_id=user.id,
        name=long_name,
        hourly_rate=None,
        remind_hour_local=None,
    )
    assert len(updated.name) == 80


async def test_complete_onboarding_skips_empty_name(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    updated = await complete_onboarding(
        session,
        user_id=user.id,
        name="   ",
        hourly_rate=None,
        remind_hour_local=None,
    )
    assert updated.name == "Old Name"


async def test_complete_onboarding_rejects_bad_hour(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    with pytest.raises(ValueError):
        await complete_onboarding(
            session,
            user_id=user.id,
            name="x",
            hourly_rate=None,
            remind_hour_local=99,
        )


async def test_complete_onboarding_missing_user_raises(
    session: AsyncSession,
) -> None:
    with pytest.raises(ValueError):
        await complete_onboarding(
            session,
            user_id=999999,
            name="x",
            hourly_rate=None,
            remind_hour_local=None,
        )
