"""Phase 6.11a: tests for the /report multi-month summary."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
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
from src.bot.handlers.report import parse_months_arg
from src.core.models import Advance, Crew, DayEntry, SalaryPayment, User
from src.services import accounting as accounting_module
from src.services.advances import SalaryBreakdown, record_advance
from src.services.reports.service import get_report_data
from src.services.reports.text import format_report_text
from src.services.salary_payments import record_payment


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


async def _seed_user(
    session: AsyncSession, *, rate: Decimal | None = Decimal("50.00"),
) -> User:
    user = User(tg_id=100, name="Worker", hourly_rate=rate, currency="PLN")
    session.add(user)
    await session.flush()
    return user


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


# --- parse_months_arg --------------------------------------------------


def test_parse_months_default_when_none() -> None:
    assert parse_months_arg(None) == 6


def test_parse_months_default_when_empty_string() -> None:
    assert parse_months_arg("") == 6
    assert parse_months_arg("   ") == 6


def test_parse_months_valid_value() -> None:
    assert parse_months_arg("12") == 12
    assert parse_months_arg(" 1 ") == 1
    assert parse_months_arg("24") == 24


def test_parse_months_out_of_range_rejected() -> None:
    assert parse_months_arg("0") is None
    assert parse_months_arg("25") is None
    assert parse_months_arg("-3") is None


def test_parse_months_non_numeric_rejected() -> None:
    assert parse_months_arg("abc") is None
    assert parse_months_arg("3.5") is None


# --- get_report_data ---------------------------------------------------


async def test_report_data_walks_back_n_months(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("160"), Decimal("8000")),
        (2026, 4): (Decimal("160"), Decimal("8000")),
        (2026, 3): (Decimal("140"), Decimal("7000")),
    })
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 12), months=3,
    )
    assert data.months == 3
    assert [(lg.year, lg.month) for lg in data.ledgers] == [
        (2026, 5), (2026, 4), (2026, 3),
    ]
    assert data.total_hours == Decimal("460.00")
    assert data.total_earnings == Decimal("23000.00")


async def test_report_data_total_owed_sums_positive_remainings(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("160"), Decimal("8000")),
        (2026, 4): (Decimal("160"), Decimal("8000")),
    })
    # April fully paid; May still owed.
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 20), months=2,
    )
    assert data.total_received == Decimal("8000.00")
    assert data.total_owed == Decimal("8000.00")  # only May
    assert data.total_overpaid == Decimal("0.00")


async def test_report_data_total_overpaid_when_received_exceeds_earnings(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("160"), Decimal("8000")),
    })
    await record_advance(
        session, user_id=user.id, amount=Decimal("9000"),
        recorded_by_id=user.id, day=date(2026, 5, 1),
        period_year=2026, period_month=5,
    )
    await session.commit()
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 31), months=1,
    )
    assert data.total_owed == Decimal("0.00")
    assert data.total_overpaid == Decimal("1000.00")


async def test_report_data_unpriced_months_dont_break_totals(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session, rate=None)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("100"), None),
        (2026, 4): (Decimal("80"), None),
    })
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 12), months=2,
    )
    assert data.total_hours == Decimal("180.00")
    assert data.total_earnings is None
    assert data.total_owed == Decimal("0.00")


# --- format_report_text ------------------------------------------------


async def test_format_report_text_contains_period_labels_and_totals(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("160"), Decimal("8000")),
        (2026, 4): (Decimal("160"), Decimal("8000")),
    })
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 20), months=2,
    )
    text = format_report_text(data, user)
    assert "Май 2026" in text
    assert "Апрель 2026" in text
    assert "PLN" in text
    # Totals row mentions debt (долг) including the May 8000 PLN.
    assert "долг 8000.00" in text


async def test_format_report_text_renders_unpriced_row(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session, rate=None)
    _stub_compute_salary(monkeypatch, by_month={
        (2026, 5): (Decimal("100"), None),
    })
    data = await get_report_data(
        session, user=user, tz=_TZ, today=date(2026, 5, 20), months=1,
    )
    text = format_report_text(data, user)
    assert "без ставки" in text
