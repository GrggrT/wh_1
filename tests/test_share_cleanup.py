"""Tests for periodic cleanup of expired share_tokens / cloud_backups."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
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
from src.core.config import Settings
from src.core.models import CloudBackup, Crew, ShareToken, User
from src.services import backup_cloud, share_cleanup
from src.services.share_cleanup import prune_expired


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES = [
    Crew.__table__,
    User.__table__,
    ShareToken.__table__,
    CloudBackup.__table__,
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


def _settings(*, enabled: bool = True) -> Settings:
    return Settings(  # type: ignore[call-arg]
        bot_token="t",
        owner_tg_id=1,
        supabase_url="https://example.supabase.co" if enabled else "",
        supabase_service_role_key="srv-key" if enabled else "",
        supabase_backups_bucket="backups",
    )


async def _add_user(s: AsyncSession, *, tg_id: int) -> User:
    u = User(tg_id=tg_id, name="U", hourly_rate=Decimal("50.00"), currency="PLN")
    s.add(u)
    await s.flush()
    return u


async def test_prune_drops_expired_share_tokens(
    session: AsyncSession,
) -> None:
    u = await _add_user(session, tg_id=1)
    now = datetime.now(tz=UTC)
    session.add_all([
        ShareToken(
            token="live", source_user_id=u.id,
            expires_at=now + timedelta(hours=1),
        ),
        ShareToken(
            token="dead", source_user_id=u.id,
            expires_at=now - timedelta(hours=1),
        ),
    ])
    await session.flush()

    result = await prune_expired(session, settings=_settings(enabled=False), now=now)
    assert result.share_tokens_deleted == 1
    remaining = (
        await session.execute(select(ShareToken.token))
    ).scalars().all()
    assert remaining == ["live"]


async def test_prune_deletes_blob_then_row(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    deleted_paths: list[str] = []

    async def fake_delete(settings: Settings, *, storage_path: str) -> None:
        deleted_paths.append(storage_path)

    monkeypatch.setattr(backup_cloud, "delete_xlsx", fake_delete)
    monkeypatch.setattr(share_cleanup, "delete_xlsx", fake_delete)

    u = await _add_user(session, tg_id=1)
    now = datetime.now(tz=UTC)
    session.add(CloudBackup(
        key="dead-key", owner_user_id=u.id,
        storage_path="user_1/dead-key.xlsx", size_bytes=100,
        expires_at=now - timedelta(hours=1),
    ))
    await session.flush()

    result = await prune_expired(session, settings=_settings(), now=now)
    assert result.cloud_backups_deleted == 1
    assert result.storage_failures == 0
    assert deleted_paths == ["user_1/dead-key.xlsx"]
    remaining = (
        await session.execute(select(CloudBackup.key))
    ).scalars().all()
    assert remaining == []


async def test_prune_skips_blob_delete_when_storage_disabled(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    async def fake_delete(*_a: object, **_kw: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(share_cleanup, "delete_xlsx", fake_delete)

    u = await _add_user(session, tg_id=1)
    now = datetime.now(tz=UTC)
    session.add(CloudBackup(
        key="k", owner_user_id=u.id,
        storage_path="p", size_bytes=1,
        expires_at=now - timedelta(hours=1),
    ))
    await session.flush()

    result = await prune_expired(
        session, settings=_settings(enabled=False), now=now,
    )
    assert called is False
    assert result.cloud_backups_deleted == 1


async def test_prune_counts_storage_failures(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_delete(*_a: object, **_kw: object) -> None:
        raise RuntimeError("503")

    monkeypatch.setattr(share_cleanup, "delete_xlsx", fake_delete)

    u = await _add_user(session, tg_id=1)
    now = datetime.now(tz=UTC)
    session.add(CloudBackup(
        key="k", owner_user_id=u.id,
        storage_path="p", size_bytes=1,
        expires_at=now - timedelta(hours=1),
    ))
    await session.flush()

    result = await prune_expired(session, settings=_settings(), now=now)
    # Row still removed even when blob delete fails.
    assert result.cloud_backups_deleted == 1
    assert result.storage_failures == 1


async def test_prune_keeps_live_rows(session: AsyncSession) -> None:
    u = await _add_user(session, tg_id=1)
    now = datetime.now(tz=UTC)
    session.add(CloudBackup(
        key="alive", owner_user_id=u.id,
        storage_path="p", size_bytes=1,
        expires_at=now + timedelta(hours=1),
    ))
    await session.flush()

    result = await prune_expired(
        session, settings=_settings(enabled=False), now=now,
    )
    assert result.cloud_backups_deleted == 0
