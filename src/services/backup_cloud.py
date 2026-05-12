"""Backup-to-cloud round-trip via Supabase Storage.

A user runs ``/backup_to_cloud``: the bot builds the same XLSX as
``/backup``, uploads it to a private Supabase Storage bucket, and
records a row in ``cloud_backups``. The opaque key returned can later
be redeemed with ``/restore_from_cloud <key>`` on any device — the
file is fetched back, parsed, and applied via :func:`apply_restore`.

Storage IO is isolated in :func:`upload_xlsx` / :func:`download_xlsx`
so tests can monkeypatch them without hitting the network. The bot
gates the commands on :func:`cloud_storage_enabled`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.models import CloudBackup, User

logger = structlog.get_logger()

# Backups live a week in cloud by default.
DEFAULT_TTL = timedelta(days=7)


class CloudBackupError(RuntimeError):
    """Raised when cloud storage is misconfigured or a redeem fails."""


@dataclass
class CloudIssued:
    key: str
    expires_at: datetime
    size_bytes: int


def cloud_storage_enabled(settings: Settings) -> bool:
    return bool(
        settings.supabase_url
        and settings.supabase_service_role_key
        and settings.supabase_backups_bucket,
    )


def _object_url(settings: Settings, storage_path: str) -> str:
    return (
        f"{settings.supabase_url.rstrip('/')}"
        f"/storage/v1/object/{settings.supabase_backups_bucket}/{storage_path}"
    )


async def upload_xlsx(
    settings: Settings, *, storage_path: str, data: bytes,
) -> None:
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            _object_url(settings, storage_path), content=data, headers=headers,
        )
    resp.raise_for_status()


async def download_xlsx(
    settings: Settings, *, storage_path: str,
) -> bytes:
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(
            _object_url(settings, storage_path), headers=headers,
        )
    resp.raise_for_status()
    return resp.content


def _build_storage_path(owner_id: int, key: str) -> str:
    return f"user_{owner_id}/{key}.xlsx"


async def register_cloud_backup(
    session: AsyncSession,
    *,
    owner: User,
    data: bytes,
    settings: Settings,
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
) -> CloudIssued:
    """Upload ``data`` to storage and persist a ``cloud_backups`` row."""
    if not cloud_storage_enabled(settings):
        raise CloudBackupError("storage_disabled")
    moment = now or datetime.now(tz=UTC)
    key = secrets.token_urlsafe(18)
    storage_path = _build_storage_path(owner.id, key)
    await upload_xlsx(settings, storage_path=storage_path, data=data)
    row = CloudBackup(
        key=key,
        owner_user_id=owner.id,
        storage_path=storage_path,
        size_bytes=len(data),
        expires_at=moment + ttl,
    )
    session.add(row)
    await session.flush()
    return CloudIssued(
        key=key, expires_at=row.expires_at, size_bytes=row.size_bytes,
    )


async def fetch_cloud_backup(
    session: AsyncSession,
    *,
    key: str,
    settings: Settings,
    now: datetime | None = None,
) -> bytes:
    """Look up ``key``, verify it's live, and return the XLSX bytes."""
    if not cloud_storage_enabled(settings):
        raise CloudBackupError("storage_disabled")
    moment = now or datetime.now(tz=UTC)
    row = (
        await session.execute(
            select(CloudBackup).where(CloudBackup.key == key),
        )
    ).scalar_one_or_none()
    if row is None:
        raise CloudBackupError("not_found")
    expires = row.expires_at
    if expires.tzinfo is None:  # sqlite round-trip drops tzinfo
        expires = expires.replace(tzinfo=UTC)
    if expires <= moment:
        raise CloudBackupError("expired")
    return await download_xlsx(settings, storage_path=row.storage_path)
