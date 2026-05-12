"""Phase 7.1b: /restore — round-trip and dedup behavior."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
import pytest_asyncio
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.core.models import Advance, Crew, DayEntry, SalaryPayment, User
from src.services.reports.backup import build_backup_xlsx
from src.services.reports.restore import (
    BackupParseError,
    apply_restore,
    parse_backup_xlsx,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES = [
    Crew.__table__,
    User.__table__,
    DayEntry.__table__,
    Advance.__table__,
    SalaryPayment.__table__,
]


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


async def _seed_user(session: AsyncSession, tg_id: int = 100) -> User:
    user = User(
        tg_id=tg_id, name="Worker",
        hourly_rate=Decimal("50.00"), currency="PLN",
    )
    session.add(user)
    await session.flush()
    return user


def _make_backup_buf(
    user: User,
    days: list[DayEntry] | None = None,
    advs: list[Advance] | None = None,
    pays: list[SalaryPayment] | None = None,
) -> BytesIO:
    return build_backup_xlsx(
        user, days or [], advs or [], pays or [], today=date(2026, 5, 12),
    )


# --- parse_backup_xlsx -------------------------------------------------


async def test_parse_recognizes_round_trip_rows(session: AsyncSession) -> None:
    user = await _seed_user(session)
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note="ok",
    )]
    advs = [Advance(
        id=2, user_id=user.id, day=date(2026, 5, 3),
        period_year=2026, period_month=5,
        amount=Decimal("200.00"), note="cash",
        recorded_by_id=user.id,
    )]
    pays = [SalaryPayment(
        id=3, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4,
        amount=Decimal("8000.00"), note=None,
        recorded_by_id=user.id,
    )]
    buf = _make_backup_buf(user, days, advs, pays)
    plan = parse_backup_xlsx(buf)
    assert len(plan.days) == 1
    assert plan.days[0].day == date(2026, 5, 1)
    assert plan.days[0].hours == Decimal("8.00")
    assert plan.advances[0].amount == Decimal("200.00")
    assert plan.advances[0].period_month == 5
    assert plan.payments[0].paid_on == date(2026, 5, 5)
    assert plan.payments[0].period_month == 4


def test_parse_rejects_workbook_missing_required_sheet() -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.title = "Профиль"  # only Profile present
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    with pytest.raises(BackupParseError):
        parse_backup_xlsx(buf)


# --- apply_restore -----------------------------------------------------


async def test_apply_restore_inserts_new_rows(session: AsyncSession) -> None:
    user = await _seed_user(session)
    days = [DayEntry(
        id=1, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note=None,
    )]
    plan = parse_backup_xlsx(_make_backup_buf(user, days=days))

    result = await apply_restore(session, user=user, plan=plan)
    await session.commit()

    assert result.days_inserted == 1
    assert result.days_skipped == 0
    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].day == date(2026, 5, 1)
    assert rows[0].hours == Decimal("8.00")


async def test_apply_restore_skips_existing_day_entry(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    # Pre-existing row with different hours: restore must NOT overwrite.
    existing = DayEntry(
        user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("4.00"), note="keep",
    )
    session.add(existing)
    await session.flush()

    days = [DayEntry(
        id=99, user_id=user.id, day=date(2026, 5, 1),
        hours=Decimal("8.00"), note="from backup",
    )]
    plan = parse_backup_xlsx(_make_backup_buf(user, days=days))
    result = await apply_restore(session, user=user, plan=plan)
    await session.commit()

    assert result.days_inserted == 0
    assert result.days_skipped == 1
    rows = (await session.execute(
        select(DayEntry).where(DayEntry.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].hours == Decimal("4.00")  # unchanged
    assert rows[0].note == "keep"


async def test_apply_restore_deduplicates_advances_by_natural_key(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    existing_adv = Advance(
        user_id=user.id, day=date(2026, 5, 3),
        period_year=2026, period_month=5,
        amount=Decimal("200.00"), note="cash",
        recorded_by_id=user.id,
    )
    session.add(existing_adv)
    await session.flush()

    advs_from_backup = [
        # Same natural key — should be skipped.
        Advance(
            id=1, user_id=user.id, day=date(2026, 5, 3),
            period_year=2026, period_month=5,
            amount=Decimal("200.00"), note="cash",
            recorded_by_id=user.id,
        ),
        # Different amount on same day — counts as new.
        Advance(
            id=2, user_id=user.id, day=date(2026, 5, 3),
            period_year=2026, period_month=5,
            amount=Decimal("50.00"), note="cash",
            recorded_by_id=user.id,
        ),
    ]
    plan = parse_backup_xlsx(_make_backup_buf(user, advs=advs_from_backup))
    result = await apply_restore(session, user=user, plan=plan)
    await session.commit()

    assert result.advances_inserted == 1
    assert result.advances_skipped == 1
    rows = (await session.execute(
        select(Advance).where(Advance.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 2
    assert sorted(r.amount for r in rows) == [
        Decimal("50.00"), Decimal("200.00"),
    ]


async def test_apply_restore_round_trips_payments(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    pays = [SalaryPayment(
        id=1, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4,
        amount=Decimal("8000.00"), note=None,
        recorded_by_id=user.id,
    )]
    plan = parse_backup_xlsx(_make_backup_buf(user, pays=pays))
    result = await apply_restore(session, user=user, plan=plan)
    await session.commit()

    assert result.payments_inserted == 1
    rows = (await session.execute(
        select(SalaryPayment).where(SalaryPayment.user_id == user.id),
    )).scalars().all()
    assert len(rows) == 1
    assert rows[0].period_month == 4
    assert rows[0].paid_on == date(2026, 5, 5)
