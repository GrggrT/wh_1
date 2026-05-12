"""Phase 6.6: salary_payments service tests.

Uses the same in-memory aiosqlite pattern as `test_db_integration` /
`test_onboarding`. Verifies the critical accounting property: payment
date and accounting period are independent.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
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
from src.core.models import Crew, SalaryPayment, User
from src.services.salary_payments import (
    list_payments_for_period,
    list_payments_paid_in_range,
    list_payments_paid_on,
    record_payment,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES_FOR_TESTS = [
    Crew.__table__,
    User.__table__,
    SalaryPayment.__table__,
]


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


async def _seed_user(session: AsyncSession, *, tg_id: int = 100) -> User:
    user = User(tg_id=tg_id, name="Worker")
    session.add(user)
    await session.flush()
    return user


async def test_record_payment_persists_paid_on_and_period(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    payment = await record_payment(
        session,
        user_id=user.id,
        paid_on=date(2026, 5, 5),
        period_year=2026,
        period_month=4,
        amount=Decimal("1500.00"),
        recorded_by_id=user.id,
        note="April salary",
    )
    assert payment.paid_on == date(2026, 5, 5)
    assert payment.period_year == 2026
    assert payment.period_month == 4
    assert payment.amount == Decimal("1500.00")
    assert payment.note == "April salary"


async def test_record_payment_rejects_bad_period(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    with pytest.raises(ValueError):
        await record_payment(
            session,
            user_id=user.id,
            paid_on=date(2026, 5, 5),
            period_year=2026,
            period_month=13,
            amount=Decimal("100"),
            recorded_by_id=user.id,
        )


async def test_record_payment_rejects_non_positive_amount(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    with pytest.raises(ValueError):
        await record_payment(
            session,
            user_id=user.id,
            paid_on=date(2026, 5, 5),
            period_year=2026,
            period_month=4,
            amount=Decimal("0"),
            recorded_by_id=user.id,
        )


async def test_list_payments_paid_on_filters_by_date(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("1000"),
        recorded_by_id=user.id,
    )
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 6),
        period_year=2026, period_month=4, amount=Decimal("250"),
        recorded_by_id=user.id,
    )
    await session.commit()

    on_5 = await list_payments_paid_on(
        session, user_id=user.id, day=date(2026, 5, 5),
    )
    assert len(on_5) == 1
    assert on_5[0].amount == Decimal("1000")


async def test_list_payments_paid_in_range_only_own_user(
    session: AsyncSession,
) -> None:
    a = await _seed_user(session, tg_id=1)
    b = await _seed_user(session, tg_id=2)
    await record_payment(
        session, user_id=a.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("1000"),
        recorded_by_id=a.id,
    )
    await record_payment(
        session, user_id=b.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("999"),
        recorded_by_id=b.id,
    )
    await session.commit()

    rows = await list_payments_paid_in_range(
        session,
        user_id=a.id,
        start=date(2026, 5, 1),
        end=date(2026, 5, 31),
    )
    assert len(rows) == 1
    assert rows[0].amount == Decimal("1000")


async def test_list_payments_for_period_matches_independent_of_paid_on(
    session: AsyncSession,
) -> None:
    """The critical accounting property: a payment for April work
    found in two physical months should both show up when queried by
    period=April."""
    user = await _seed_user(session)
    # Paid May 5 covering April.
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("1500"),
        recorded_by_id=user.id,
    )
    # A late top-up paid June 1 also covering April.
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 6, 1),
        period_year=2026, period_month=4, amount=Decimal("200"),
        recorded_by_id=user.id,
    )
    # Unrelated payment for May period.
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 6, 5),
        period_year=2026, period_month=5, amount=Decimal("1700"),
        recorded_by_id=user.id,
    )
    await session.commit()

    rows = await list_payments_for_period(
        session, user_id=user.id, period_year=2026, period_month=4,
    )
    assert len(rows) == 2
    total = sum((r.amount for r in rows), Decimal(0))
    assert total == Decimal("1700")
