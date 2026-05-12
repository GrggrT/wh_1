"""Tests for /backup_to_cloud + /restore_from_cloud service layer."""

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
from src.core.config import Settings
from src.core.models import CloudBackup, Crew, User
from src.services import backup_cloud
from src.services.backup_cloud import (
    CloudBackupError,
    cloud_storage_enabled,
    fetch_cloud_backup,
    register_cloud_backup,
)


@compiles(BigInteger, "sqlite")
def _bigint_as_integer_on_sqlite(*_args: object, **_kw: object) -> str:
    return "INTEGER"


_TABLES = [Crew.__table__, User.__table__, CloudBackup.__table__]


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


def test_cloud_storage_enabled_requires_full_config() -> None:
    assert not cloud_storage_enabled(_settings(enabled=False))
    assert cloud_storage_enabled(_settings(enabled=True))


async def test_register_uploads_and_records(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_upload(
        settings: Settings, *, storage_path: str, data: bytes,
    ) -> None:
        captured["path"] = storage_path
        captured["size"] = len(data)

    monkeypatch.setattr(backup_cloud, "upload_xlsx", fake_upload)
    u = await _add_user(session, tg_id=42)
    issued = await register_cloud_backup(
        session, owner=u, data=b"x" * 128, settings=_settings(),
    )
    assert issued.size_bytes == 128
    assert captured["size"] == 128
    assert isinstance(captured["path"], str)
    assert captured["path"].startswith(f"user_{u.id}/")
    assert captured["path"].endswith(".xlsx")


async def test_fetch_returns_bytes_from_storage(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_upload(*_a: object, **_kw: object) -> None:
        return None

    async def fake_download(
        settings: Settings, *, storage_path: str,
    ) -> bytes:
        assert storage_path.endswith(".xlsx")
        return b"PAYLOAD"

    monkeypatch.setattr(backup_cloud, "upload_xlsx", fake_upload)
    monkeypatch.setattr(backup_cloud, "download_xlsx", fake_download)

    u = await _add_user(session, tg_id=42)
    issued = await register_cloud_backup(
        session, owner=u, data=b"x", settings=_settings(),
    )
    data = await fetch_cloud_backup(
        session, key=issued.key, settings=_settings(),
    )
    assert data == b"PAYLOAD"


async def test_fetch_unknown_key_raises(session: AsyncSession) -> None:
    with pytest.raises(CloudBackupError, match="not_found"):
        await fetch_cloud_backup(
            session, key="ghost", settings=_settings(),
        )


async def test_fetch_expired_raises(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_upload(*_a: object, **_kw: object) -> None:
        return None

    monkeypatch.setattr(backup_cloud, "upload_xlsx", fake_upload)
    u = await _add_user(session, tg_id=42)
    past = datetime.now(tz=UTC) - timedelta(days=10)
    issued = await register_cloud_backup(
        session, owner=u, data=b"x", settings=_settings(),
        ttl=timedelta(hours=-1), now=past,
    )
    with pytest.raises(CloudBackupError, match="expired"):
        await fetch_cloud_backup(
            session, key=issued.key, settings=_settings(),
        )


async def test_register_rejects_when_storage_disabled(
    session: AsyncSession,
) -> None:
    u = await _add_user(session, tg_id=42)
    with pytest.raises(CloudBackupError, match="storage_disabled"):
        await register_cloud_backup(
            session, owner=u, data=b"x", settings=_settings(enabled=False),
        )
