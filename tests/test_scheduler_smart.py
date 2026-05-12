"""Phase 7.2 follow-up: scheduler dedup tests for smart reminders."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
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
from src.bot import scheduler_runner
from src.core.models import Advance, Crew, DayEntry, SalaryPayment, User
from src.services import accounting as accounting_module
from src.services.advances import SalaryBreakdown


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

_TZ = ZoneInfo("Europe/Warsaw")


@dataclass
class _FakeSettings:
    timezone: str = "Europe/Warsaw"
    daily_digest_hour: int = 9


class _FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **_kw: object) -> None:
        self.sent.append((chat_id, text))


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


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    scheduler_runner._last_gap_nudge_by_user.clear()
    scheduler_runner._last_debt_ping_iso_week_by_user.clear()


def _patch_session(monkeypatch: pytest.MonkeyPatch, session: AsyncSession) -> None:
    async def fake_get_session() -> AsyncIterator[AsyncSession]:
        yield session

    monkeypatch.setattr(scheduler_runner, "get_session", fake_get_session)


def _patch_now(
    monkeypatch: pytest.MonkeyPatch, *, when: datetime,
) -> None:
    monkeypatch.setattr(scheduler_runner, "_now_local", lambda _tz: when)


def _stub_compute_salary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    by_month: dict[tuple[int, int], tuple[Decimal, Decimal | None]],
) -> None:
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


async def _seed_user(s: AsyncSession, *, tg_id: int = 111) -> User:
    u = User(
        tg_id=tg_id,
        name="Иван",
        locale="ru",
        currency="PLN",
        role="worker",
        hourly_rate=Decimal("30.00"),
        created_at=datetime(2025, 1, 1, tzinfo=UTC),
    )
    s.add(u)
    await s.commit()
    await s.refresh(u)
    return u


# --- gap nudges -------------------------------------------------------


@pytest.mark.asyncio
async def test_gap_nudge_sends_once_per_day(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    await _seed_user(session)
    when = datetime(2026, 5, 12, 10, 0, tzinfo=_TZ)
    _patch_now(monkeypatch, when=when)

    bot = _FakeBot()
    settings = _FakeSettings()
    await scheduler_runner._maybe_send_gap_nudges(bot, settings)  # type: ignore[arg-type]
    assert len(bot.sent) == 1

    # Second invocation on the same simulated day must NOT resend.
    await scheduler_runner._maybe_send_gap_nudges(bot, settings)  # type: ignore[arg-type]
    assert len(bot.sent) == 1


@pytest.mark.asyncio
async def test_gap_nudge_skips_before_digest_hour(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    await _seed_user(session)
    # 08:00 local < daily_digest_hour=9 → nothing sent.
    _patch_now(monkeypatch, when=datetime(2026, 5, 12, 8, 0, tzinfo=_TZ))
    bot = _FakeBot()
    settings = _FakeSettings()
    await scheduler_runner._maybe_send_gap_nudges(bot, settings)  # type: ignore[arg-type]
    assert bot.sent == []


@pytest.mark.asyncio
async def test_gap_nudge_resets_on_new_day(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    await _seed_user(session)
    bot = _FakeBot()
    settings = _FakeSettings()

    _patch_now(monkeypatch, when=datetime(2026, 5, 12, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_gap_nudges(bot, settings)  # type: ignore[arg-type]
    _patch_now(monkeypatch, when=datetime(2026, 5, 13, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_gap_nudges(bot, settings)  # type: ignore[arg-type]
    assert len(bot.sent) == 2


# --- debt pings -------------------------------------------------------


@pytest.mark.asyncio
async def test_debt_ping_only_on_monday(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    user = await _seed_user(session)
    # March 2026 owed (8h @ 30 = 240 PLN), no payments.
    _stub_compute_salary(
        monkeypatch,
        by_month={(2026, 3): (Decimal("8"), Decimal("240.00"))},
    )
    session.add(DayEntry(user_id=user.id, day=date(2026, 3, 1), hours=Decimal("8")))
    await session.commit()

    bot = _FakeBot()
    settings = _FakeSettings()
    # Tuesday May 12, 2026 → must NOT send.
    _patch_now(monkeypatch, when=datetime(2026, 5, 12, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_debt_pings(bot, settings)  # type: ignore[arg-type]
    assert bot.sent == []

    # Monday May 11, 2026 → must send once.
    _patch_now(monkeypatch, when=datetime(2026, 5, 11, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_debt_pings(bot, settings)  # type: ignore[arg-type]
    assert len(bot.sent) == 1
    assert "Март 2026" in bot.sent[0][1]


@pytest.mark.asyncio
async def test_debt_ping_dedups_within_iso_week(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    user = await _seed_user(session)
    _stub_compute_salary(
        monkeypatch,
        by_month={(2026, 3): (Decimal("8"), Decimal("240.00"))},
    )
    session.add(DayEntry(user_id=user.id, day=date(2026, 3, 1), hours=Decimal("8")))
    await session.commit()

    bot = _FakeBot()
    settings = _FakeSettings()
    _patch_now(monkeypatch, when=datetime(2026, 5, 11, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_debt_pings(bot, settings)  # type: ignore[arg-type]
    await scheduler_runner._maybe_send_debt_pings(bot, settings)  # type: ignore[arg-type]
    assert len(bot.sent) == 1


@pytest.mark.asyncio
async def test_debt_ping_silent_when_nothing_aged(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_session(monkeypatch, session)
    await _seed_user(session)
    # No DayEntry, no aged debt.
    _stub_compute_salary(monkeypatch, by_month={})

    bot = _FakeBot()
    settings = _FakeSettings()
    _patch_now(monkeypatch, when=datetime(2026, 5, 11, 10, 0, tzinfo=_TZ))
    await scheduler_runner._maybe_send_debt_pings(bot, settings)  # type: ignore[arg-type]
    assert bot.sent == []
