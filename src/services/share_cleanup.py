"""Periodic cleanup for /share_backup + /backup_to_cloud artefacts.

Both share_tokens and cloud_backups carry ``expires_at`` columns but
nothing prunes them automatically. This module is invoked from the
scheduler loop hourly. The cloud variant deletes the underlying object
from Supabase Storage before dropping the DB row to avoid orphaned
blobs; storage failures are logged but do not block DB cleanup.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.models import CloudBackup, ShareToken
from src.services.backup_cloud import cloud_storage_enabled, delete_xlsx

logger = structlog.get_logger()


@dataclass
class CleanupResult:
    share_tokens_deleted: int
    cloud_backups_deleted: int
    storage_failures: int


async def prune_expired(
    session: AsyncSession,
    *,
    settings: Settings,
    now: datetime | None = None,
) -> CleanupResult:
    moment = now or datetime.now(tz=UTC)
    tokens_deleted = await _prune_share_tokens(session, moment=moment)
    cloud_deleted, storage_failures = await _prune_cloud_backups(
        session, settings=settings, moment=moment,
    )
    return CleanupResult(
        share_tokens_deleted=tokens_deleted,
        cloud_backups_deleted=cloud_deleted,
        storage_failures=storage_failures,
    )


async def _prune_share_tokens(
    session: AsyncSession, *, moment: datetime,
) -> int:
    result = await session.execute(
        delete(ShareToken).where(ShareToken.expires_at < moment),
    )
    return int(result.rowcount or 0)


async def _prune_cloud_backups(
    session: AsyncSession, *, settings: Settings, moment: datetime,
) -> tuple[int, int]:
    rows = (
        await session.execute(
            select(CloudBackup).where(CloudBackup.expires_at < moment),
        )
    ).scalars().all()
    if not rows:
        return 0, 0

    storage_failures = 0
    if cloud_storage_enabled(settings):
        for row in rows:
            try:
                await delete_xlsx(
                    settings, storage_path=row.storage_path,
                )
            except Exception:  # noqa: BLE001 — best-effort
                storage_failures += 1
                logger.warning(
                    "cloud_backup_blob_delete_failed",
                    key=row.key, storage_path=row.storage_path,
                )

    deleted_keys = [r.key for r in rows]
    await session.execute(
        delete(CloudBackup).where(CloudBackup.key.in_(deleted_keys)),
    )
    return len(deleted_keys), storage_failures
