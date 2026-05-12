"""Phase 6.9: tests for the /profile editor.

The handler is a thin DB updater, so we focus on:
  - the user-facing render (`_render_profile`) for the various states,
  - currency code validation regex,
  - DB round-trip for `User.currency` (defaults + update via the model).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles
from src.bot.handlers.profile import _CURRENCY_RE, _render_profile
from src.core.models import Crew, User


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        for table in (Crew.__table__, User.__table__):
            await conn.run_sync(table.create)  # type: ignore[attr-defined]
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


def _user(
    *,
    name: str = "Worker",
    rate: Decimal | None = None,
    currency: str = "PLN",
    hour: int | None = None,
) -> User:
    return User(  # type: ignore[call-arg]
        tg_id=1,
        name=name,
        hourly_rate=rate,
        currency=currency,
        remind_hour_local=hour,
    )


def test_render_profile_minimal() -> None:
    out = _render_profile(_user(name="Alice"))
    assert "Alice" in out
    assert "не задана" in out
    assert "PLN" in out
    assert "выключено" in out


def test_render_profile_full() -> None:
    out = _render_profile(
        _user(name="Bob", rate=Decimal("42.50"), currency="EUR", hour=19),
    )
    assert "Bob" in out
    assert "42.50 EUR/ч" in out
    assert "EUR" in out
    assert "19:00" in out


def test_currency_regex_accepts_valid_codes() -> None:
    for code in ("PLN", "USD", "EUR", "RUB", "BYN", "UAH"):
        assert _CURRENCY_RE.fullmatch(code)


def test_currency_regex_rejects_bad_codes() -> None:
    for bad in ("PL", "PLNN", "12X", "PL N", "", "поль"):
        assert not _CURRENCY_RE.fullmatch(bad)


async def test_user_currency_default_is_pln(session: AsyncSession) -> None:
    u = User(tg_id=42, name="N")  # type: ignore[call-arg]
    session.add(u)
    await session.flush()
    await session.refresh(u)
    assert u.currency == "PLN"


async def test_user_currency_can_be_updated(session: AsyncSession) -> None:
    u = User(tg_id=43, name="N")  # type: ignore[call-arg]
    session.add(u)
    await session.flush()
    u.currency = "USD"
    await session.commit()
    fetched = (
        await session.execute(select(User).where(User.tg_id == 43))
    ).scalar_one()
    assert fetched.currency == "USD"


async def test_user_currency_affects_render(session: AsyncSession) -> None:
    u = User(  # type: ignore[call-arg]
        tg_id=44,
        name="N",
        hourly_rate=Decimal("30"),
        currency="UAH",
        remind_hour_local=20,
        day_reminder_last_sent=date(2026, 5, 1),
    )
    session.add(u)
    await session.commit()
    text = _render_profile(u)
    assert "UAH" in text
    assert "30 UAH/ч" in text
