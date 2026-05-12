"""Tests for the share-token-based cross-account /restore_from flow."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
from src.core.models import (
    Advance,
    Crew,
    DayEntry,
    SalaryPayment,
    ShareToken,
    User,
)
from src.services.share_backup import (
    ShareTokenError,
    issue_share_token,
    peek_share_token,
    redeem_share_token,
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
    ShareToken.__table__,
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


async def _add_user(
    s: AsyncSession, *, tg_id: int, name: str,
) -> User:
    u = User(tg_id=tg_id, name=name, hourly_rate=Decimal("50.00"), currency="PLN")
    s.add(u)
    await s.flush()
    return u


async def test_issue_share_token_creates_row(session: AsyncSession) -> None:
    u = await _add_user(session, tg_id=1, name="A")
    issued = await issue_share_token(session, source_user=u)
    assert issued.token
    assert issued.expires_at > datetime.now(tz=UTC)


async def test_redeem_token_copies_data_to_new_user(
    session: AsyncSession,
) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    dst = await _add_user(session, tg_id=2, name="Dst")
    session.add(DayEntry(
        user_id=src.id, day=datetime(2026, 5, 1).date(),
        hours=Decimal("8.00"), note=None,
    ))
    await session.flush()

    issued = await issue_share_token(session, source_user=src)
    result = await redeem_share_token(
        session, token=issued.token, redeemer=dst,
    )
    assert result.days_inserted == 1
    assert result.days_skipped == 0


async def test_redeem_unknown_token_raises(session: AsyncSession) -> None:
    dst = await _add_user(session, tg_id=2, name="Dst")
    with pytest.raises(ShareTokenError, match="not_found"):
        await redeem_share_token(session, token="garbage", redeemer=dst)


async def test_redeem_twice_raises_already_redeemed(
    session: AsyncSession,
) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    dst = await _add_user(session, tg_id=2, name="Dst")
    issued = await issue_share_token(session, source_user=src)
    await redeem_share_token(session, token=issued.token, redeemer=dst)
    with pytest.raises(ShareTokenError, match="already_redeemed"):
        await redeem_share_token(session, token=issued.token, redeemer=dst)


async def test_redeem_expired_token_raises(session: AsyncSession) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    dst = await _add_user(session, tg_id=2, name="Dst")
    past = datetime.now(tz=UTC) - timedelta(days=1)
    issued = await issue_share_token(
        session, source_user=src, ttl=timedelta(hours=-1), now=past,
    )
    with pytest.raises(ShareTokenError, match="expired"):
        await redeem_share_token(session, token=issued.token, redeemer=dst)


async def test_redeem_by_same_user_rejected(session: AsyncSession) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    issued = await issue_share_token(session, source_user=src)
    with pytest.raises(ShareTokenError, match="same_user"):
        await redeem_share_token(session, token=issued.token, redeemer=src)


async def test_peek_returns_plan_without_consuming(
    session: AsyncSession,
) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    dst = await _add_user(session, tg_id=2, name="Dst")
    session.add(DayEntry(
        user_id=src.id, day=datetime(2026, 5, 1).date(),
        hours=Decimal("8.00"), note=None,
    ))
    await session.flush()

    issued = await issue_share_token(session, source_user=src)
    plan = await peek_share_token(
        session, token=issued.token, redeemer=dst,
    )
    assert len(plan.days) == 1
    # Token still redeemable — peek didn't consume.
    result = await redeem_share_token(
        session, token=issued.token, redeemer=dst,
    )
    assert result.days_inserted == 1


async def test_peek_invalid_token_raises(session: AsyncSession) -> None:
    dst = await _add_user(session, tg_id=2, name="Dst")
    with pytest.raises(ShareTokenError, match="not_found"):
        await peek_share_token(session, token="garbage", redeemer=dst)


async def test_issue_rate_limit_caps_active_tokens(
    session: AsyncSession,
) -> None:
    u = await _add_user(session, tg_id=1, name="A")
    for _ in range(3):
        await issue_share_token(session, source_user=u, max_active=3)
    with pytest.raises(ShareTokenError, match="rate_limited"):
        await issue_share_token(session, source_user=u, max_active=3)


async def test_issue_rate_limit_ignores_expired_and_redeemed(
    session: AsyncSession,
) -> None:
    src = await _add_user(session, tg_id=1, name="Src")
    dst = await _add_user(session, tg_id=2, name="Dst")
    # One expired token + one redeemed token shouldn't count toward the cap.
    past = datetime.now(tz=UTC) - timedelta(days=2)
    await issue_share_token(
        session, source_user=src, ttl=timedelta(hours=-1), now=past,
    )
    issued = await issue_share_token(session, source_user=src)
    await redeem_share_token(session, token=issued.token, redeemer=dst)
    # With cap=2, we should still be able to issue one fresh token.
    fresh = await issue_share_token(
        session, source_user=src, max_active=2,
    )
    assert fresh.token
