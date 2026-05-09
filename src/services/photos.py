"""Persist shift photos in Supabase Storage.

Telegram only retains photos as long as their cache permits, so we mirror them
to a private Supabase Storage bucket and keep the resulting object path on the
shift row. Uploads are best-effort: if Storage is not configured or fails, the
caller falls back to the Telegram file_id alone.
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import httpx
import structlog

_UTC = ZoneInfo("UTC")

if TYPE_CHECKING:
    from aiogram import Bot

    from src.core.config import Settings

logger = structlog.get_logger()


def _build_object_path(shift_id: int, kind: str, now: datetime) -> str:
    """Storage path: shifts/YYYY/MM/DD/<shift_id>_<kind>_<HHMMSS>.jpg."""
    return (
        f"shifts/{now:%Y/%m/%d}/{shift_id}_{kind}_{now:%H%M%S}.jpg"
    )


def storage_enabled(settings: Settings) -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key)


async def _download_telegram_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    if file.file_path is None:
        raise RuntimeError("telegram file has no path")
    buffer = BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    return buffer.getvalue()


async def _upload_to_supabase(
    settings: Settings,
    object_path: str,
    data: bytes,
) -> None:
    url = (
        f"{settings.supabase_url.rstrip('/')}"
        f"/storage/v1/object/{settings.supabase_storage_bucket}/{object_path}"
    )
    headers = {
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "apikey": settings.supabase_service_role_key,
        "Content-Type": "image/jpeg",
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, content=data, headers=headers)
    response.raise_for_status()


async def archive_shift_photo(
    bot: Bot,
    settings: Settings,
    shift_id: int,
    kind: str,
    file_id: str,
    now: datetime | None = None,
) -> str | None:
    """Download a Telegram photo and upload to Supabase Storage.

    Returns the object path on success, or None when Storage is disabled or
    the upload fails (logged, never raised — caller still keeps file_id).
    """
    if not storage_enabled(settings):
        return None
    timestamp = now or datetime.now(tz=_UTC)
    object_path = _build_object_path(shift_id, kind, timestamp)
    try:
        data = await _download_telegram_file(bot, file_id)
        await _upload_to_supabase(settings, object_path, data)
    except (httpx.HTTPError, RuntimeError, OSError):
        logger.warning(
            "photo_archive_failed",
            shift_id=shift_id,
            kind=kind,
        )
        return None
    return object_path
