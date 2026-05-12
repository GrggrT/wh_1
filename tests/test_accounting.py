"""Phase 6.7: tests for the period/cashflow/owed accounting layer.

Two flavors:

1. Pure ``PeriodLedger`` property tests — no DB. Verifies the status
   state machine (pending/partial/settled/overpaid/unpriced) and the
   settled-threshold rounding behavior.
2. Integration tests using aiosqlite for the *accounting-specific*
   tables (User, Advance, SalaryPayment, DayEntry). ``compute_salary``
   is stubbed so the tests don't need the PostGIS-only Shift/Site
   schema, but the accounting service's own logic — filtering by
   declared period, summing across multiple payments, walking back N
   months for /owed — runs against real SQL.
"""

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
from src.core.models import (
    Advance,
    Crew,
    DayEntry,
    SalaryPayment,
    User,
)
from src.services import accounting as accounting_module
from src.services.accounting import (
    SETTLED_THRESHOLD,
    PeriodLedger,
    get_period_ledger,
    list_cashflow,
    list_open_periods,
)
from src.services.advances import (
    SalaryBreakdown,
    list_advances_for_period,
    record_advance,
)
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
    session: AsyncSession, *, tg_id: int = 100, rate: Decimal | None = Decimal("50.00"),
) -> User:
    user = User(tg_id=tg_id, name="Worker", hourly_rate=rate)
    session.add(user)
    await session.flush()
    return user


def _stub_compute_salary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hours: Decimal,
    earnings: Decimal | None,
) -> None:
    """Replace compute_salary with a deterministic stub.

    This isolates accounting tests from the (PostGIS-dependent) Shift
    machinery. The accounting layer only reads ``total_hours`` and
    ``total_earnings`` off the breakdown, so other fields can be zero.
    """

    async def _fake(
        session: AsyncSession,  # noqa: ARG001
        *,
        user: User,
        year: int,
        month: int,
        tz: ZoneInfo,  # noqa: ARG001
    ) -> SalaryBreakdown:
        return SalaryBreakdown(
            user_id=user.id,
            year=year,
            month=month,
            day_entries_hours=hours,
            day_entries_earnings=earnings,
            shifts_hours=Decimal(0),
            shifts_earnings=None,
            advances_total=Decimal(0),
            net_payable=earnings,
        )

    monkeypatch.setattr(accounting_module, "compute_salary", _fake)


# --- Pure dataclass logic ---------------------------------------------------


def _ledger(
    *,
    earnings: Decimal | None,
    advances: Decimal = Decimal(0),
    payments: Decimal = Decimal(0),
) -> PeriodLedger:
    advs: list[Advance] = []
    pays: list[SalaryPayment] = []
    if advances > 0:
        advs.append(
            Advance(  # type: ignore[call-arg]
                user_id=1, day=date(2026, 4, 10),
                amount=advances, recorded_by_id=1,
            ),
        )
    if payments > 0:
        pays.append(
            SalaryPayment(  # type: ignore[call-arg]
                user_id=1, paid_on=date(2026, 5, 5),
                period_year=2026, period_month=4,
                amount=payments, recorded_by_id=1,
            ),
        )
    return PeriodLedger(
        user_id=1, year=2026, month=4,
        hours=Decimal("160"), earnings=earnings,
        advances=advs, payments=pays,
    )


def test_status_unpriced_when_no_rate() -> None:
    led = _ledger(earnings=None)
    assert led.status == "unpriced"
    assert led.remaining is None


def test_status_pending_when_nothing_paid() -> None:
    led = _ledger(earnings=Decimal("8000"))
    assert led.status == "pending"
    assert led.remaining == Decimal("8000.00")


def test_status_partial_when_some_paid() -> None:
    led = _ledger(earnings=Decimal("8000"), payments=Decimal("3000"))
    assert led.status == "partial"
    assert led.remaining == Decimal("5000.00")


def test_status_settled_when_paid_in_full() -> None:
    led = _ledger(earnings=Decimal("8000"), payments=Decimal("8000"))
    assert led.status == "settled"
    assert led.remaining == Decimal("0.00")


def test_status_settled_within_threshold() -> None:
    # 0.50 PLN diff should still count as settled (copeck rounding).
    led = _ledger(earnings=Decimal("8000.00"), payments=Decimal("7999.50"))
    assert abs(led.remaining or Decimal(0)) < SETTLED_THRESHOLD
    assert led.status == "settled"


def test_status_overpaid_when_received_exceeds() -> None:
    led = _ledger(earnings=Decimal("8000"), payments=Decimal("9000"))
    assert led.status == "overpaid"
    assert led.remaining == Decimal("-1000.00")


def test_received_total_sums_advances_and_payments() -> None:
    led = _ledger(
        earnings=Decimal("8000"),
        advances=Decimal("500"),
        payments=Decimal("3000"),
    )
    assert led.received_total == Decimal("3500.00")
    assert led.status == "partial"


# --- Integration: get_period_ledger ----------------------------------------


async def test_period_ledger_attributes_payment_by_period_not_paid_on(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A payment paid on May 5 *for* April work belongs to April's ledger."""
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()

    apr = await get_period_ledger(
        session, user=user, year=2026, month=4, tz=_TZ,
    )
    may = await get_period_ledger(
        session, user=user, year=2026, month=5, tz=_TZ,
    )
    assert len(apr.payments) == 1
    assert apr.payments[0].amount == Decimal("8000")
    assert apr.status == "settled"
    assert len(may.payments) == 0


async def test_period_ledger_collects_advances_in_calendar_month(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    await record_advance(
        session, user_id=user.id, amount=Decimal("500"),
        recorded_by_id=user.id, day=date(2026, 4, 15),
    )
    await record_advance(
        session, user_id=user.id, amount=Decimal("300"),
        recorded_by_id=user.id, day=date(2026, 5, 1),
    )
    await session.commit()

    apr = await get_period_ledger(
        session, user=user, year=2026, month=4, tz=_TZ,
    )
    assert apr.advances_total == Decimal("500.00")
    assert apr.status == "partial"
    assert apr.remaining == Decimal("7500.00")


async def test_period_ledger_partial_with_late_top_up(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A late top-up paid in June for April work should appear in April's ledger."""
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("7000"),
        recorded_by_id=user.id,
    )
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 6, 1),
        period_year=2026, period_month=4, amount=Decimal("1000"),
        recorded_by_id=user.id,
    )
    await session.commit()

    apr = await get_period_ledger(
        session, user=user, year=2026, month=4, tz=_TZ,
    )
    assert len(apr.payments) == 2
    assert apr.payments_total == Decimal("8000.00")
    assert apr.status == "settled"


# --- Integration: list_cashflow --------------------------------------------


async def test_list_cashflow_returns_both_kinds_in_month(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    await record_advance(
        session, user_id=user.id, amount=Decimal("500"),
        recorded_by_id=user.id, day=date(2026, 5, 10),
    )
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()

    rows = await list_cashflow(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 31),
    )
    assert len(rows) == 2
    kinds = sorted(r.kind for r in rows)
    assert kinds == ["advance", "payment"]


async def test_list_cashflow_payment_carries_declared_period(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()

    rows = await list_cashflow(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 31),
    )
    assert len(rows) == 1
    entry = rows[0]
    assert entry.kind == "payment"
    assert entry.day == date(2026, 5, 5)
    assert (entry.period_year, entry.period_month) == (2026, 4)


# --- Integration: list_open_periods ----------------------------------------


async def test_list_open_periods_finds_unpaid_past_period(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """April salary not yet paid → /owed must surface it from May."""
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    today = date(2026, 5, 20)
    open_periods = await list_open_periods(
        session, user=user, tz=_TZ, today=today, lookback_months=3,
    )
    months = {(p.year, p.month) for p in open_periods}
    assert (2026, 4) in months
    assert (2026, 5) in months  # May is also unpaid right now


async def test_list_open_periods_excludes_settled(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    # Pay April in full (in May).
    await record_payment(
        session, user_id=user.id, paid_on=date(2026, 5, 5),
        period_year=2026, period_month=4, amount=Decimal("8000"),
        recorded_by_id=user.id,
    )
    await session.commit()

    open_periods = await list_open_periods(
        session, user=user, tz=_TZ, today=date(2026, 5, 20),
        lookback_months=3,
    )
    months = {(p.year, p.month) for p in open_periods}
    assert (2026, 4) not in months  # settled — not owed
    assert (2026, 5) in months      # current month still unpaid


# --- Phase 6.10a: month picker keyboard ---------------------------------


def test_shift_month_back_within_year() -> None:
    from src.bot.handlers.accounting import _shift_month
    assert _shift_month(2026, 5, -1) == (2026, 4)


def test_shift_month_rolls_over_january() -> None:
    from src.bot.handlers.accounting import _shift_month
    assert _shift_month(2026, 1, -1) == (2025, 12)
    assert _shift_month(2026, 3, -6) == (2025, 9)


def test_period_picker_keyboard_has_six_months_plus_older() -> None:
    from src.bot.handlers.accounting import period_picker_keyboard
    kb = period_picker_keyboard(2026, 5)
    # 3 rows of 2 months + 1 row for «Раньше».
    assert len(kb.inline_keyboard) == 4
    cb_first = kb.inline_keyboard[0][0].callback_data or ""
    cb_last_month = kb.inline_keyboard[2][1].callback_data or ""
    older = kb.inline_keyboard[3][0].callback_data or ""
    assert cb_first.endswith("2026-05")  # anchor month = newest
    assert cb_last_month.endswith("2025-12")  # 6th-back from May 2026
    assert older.startswith("per:older:")
    assert older.endswith("2025-11")  # anchor shifts back by page_size


def test_period_picker_keyboard_callback_data_fits_64_bytes() -> None:
    from src.bot.handlers.accounting import period_picker_keyboard
    kb = period_picker_keyboard(2026, 12)
    for row in kb.inline_keyboard:
        for btn in row:
            assert btn.callback_data is not None
            assert len(btn.callback_data.encode("utf-8")) <= 64


# --- Phase 6.10b: advance ↔ period attribution -------------------------


async def test_record_advance_defaults_period_to_day(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    adv = await record_advance(
        session, user_id=user.id, amount=Decimal("100"),
        recorded_by_id=user.id, day=date(2026, 5, 10),
    )
    assert (adv.period_year, adv.period_month) == (2026, 5)


async def test_record_advance_explicit_period_overrides_day(
    session: AsyncSession,
) -> None:
    """An advance physically paid May 5 may cover the April period."""
    user = await _seed_user(session)
    adv = await record_advance(
        session, user_id=user.id, amount=Decimal("200"),
        recorded_by_id=user.id, day=date(2026, 5, 5),
        period_year=2026, period_month=4,
    )
    assert adv.day == date(2026, 5, 5)
    assert (adv.period_year, adv.period_month) == (2026, 4)


async def test_period_ledger_uses_declared_period_for_advances(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Advance paid May 5 for April → counts toward April, NOT May."""
    user = await _seed_user(session)
    _stub_compute_salary(monkeypatch, hours=Decimal("160"), earnings=Decimal("8000"))

    await record_advance(
        session, user_id=user.id, amount=Decimal("500"),
        recorded_by_id=user.id, day=date(2026, 5, 5),
        period_year=2026, period_month=4,
    )
    await session.commit()

    apr = await get_period_ledger(
        session, user=user, year=2026, month=4, tz=_TZ,
    )
    may = await get_period_ledger(
        session, user=user, year=2026, month=5, tz=_TZ,
    )
    assert apr.advances_total == Decimal("500.00")
    assert may.advances_total == Decimal("0.00")


async def test_cashflow_attributes_advance_to_declared_period(
    session: AsyncSession,
) -> None:
    """/cash for May shows the May-5 advance with April period tag."""
    user = await _seed_user(session)
    await record_advance(
        session, user_id=user.id, amount=Decimal("500"),
        recorded_by_id=user.id, day=date(2026, 5, 5),
        period_year=2026, period_month=4,
    )
    await session.commit()
    rows = await list_cashflow(
        session, user=user, start=date(2026, 5, 1), end=date(2026, 5, 31),
    )
    assert len(rows) == 1
    assert rows[0].kind == "advance"
    assert (rows[0].period_year, rows[0].period_month) == (2026, 4)


async def test_list_advances_for_period_filters_by_declared_period(
    session: AsyncSession,
) -> None:
    user = await _seed_user(session)
    # April advance, paid in April.
    await record_advance(
        session, user_id=user.id, amount=Decimal("100"),
        recorded_by_id=user.id, day=date(2026, 4, 20),
    )
    # April advance, paid late on May 5.
    await record_advance(
        session, user_id=user.id, amount=Decimal("200"),
        recorded_by_id=user.id, day=date(2026, 5, 5),
        period_year=2026, period_month=4,
    )
    # May advance, paid in May.
    await record_advance(
        session, user_id=user.id, amount=Decimal("300"),
        recorded_by_id=user.id, day=date(2026, 5, 10),
    )
    await session.commit()
    apr = await list_advances_for_period(
        session, user_id=user.id, year=2026, month=4,
    )
    assert sum((a.amount for a in apr), Decimal(0)) == Decimal("300")
    may = await list_advances_for_period(
        session, user_id=user.id, year=2026, month=5,
    )
    assert sum((a.amount for a in may), Decimal(0)) == Decimal("300")
