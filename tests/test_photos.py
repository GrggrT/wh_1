"""Tests for the photo archive service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import httpx
import pytest
from src.core.config import Settings
from src.services.photos import (
    _build_object_path,
    archive_shift_photo,
    storage_enabled,
)


def _settings(enabled: bool = True) -> Settings:
    return Settings(  # type: ignore[call-arg]
        bot_token="x",
        owner_tg_id=1,
        supabase_url="https://example.supabase.co" if enabled else "",
        supabase_service_role_key="key" if enabled else "",
        supabase_storage_bucket="shift-photos",
    )


def test_object_path_layout() -> None:
    now = datetime(2026, 5, 9, 14, 7, 33, tzinfo=ZoneInfo("UTC"))
    path = _build_object_path(42, "start", now)
    assert path == "shifts/2026/05/09/42_start_140733.jpg"


def test_storage_enabled_requires_both_values() -> None:
    assert storage_enabled(_settings(enabled=True)) is True
    assert storage_enabled(_settings(enabled=False)) is False


@pytest.mark.asyncio
async def test_archive_returns_none_when_disabled() -> None:
    bot = MagicMock()
    result = await archive_shift_photo(
        bot, _settings(enabled=False), 1, "start", "file_id",
    )
    assert result is None


@pytest.mark.asyncio
async def test_archive_uploads_and_returns_path() -> None:
    bot = MagicMock()
    file_meta = MagicMock(file_path="photos/abc.jpg")
    bot.get_file = AsyncMock(return_value=file_meta)

    async def fake_download(_path: str, destination: object) -> None:
        destination.write(b"fake-bytes")  # type: ignore[attr-defined]

    bot.download_file = AsyncMock(side_effect=fake_download)

    sent_url: dict[str, str] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, url: str, content: bytes, headers: dict[str, str]) -> FakeResponse:
            sent_url["url"] = url
            sent_url["body"] = content.decode()
            return FakeResponse()

    now = datetime(2026, 5, 9, 14, 0, 0, tzinfo=ZoneInfo("UTC"))
    with patch.object(httpx, "AsyncClient", FakeClient):
        result = await archive_shift_photo(
            bot, _settings(enabled=True), 7, "end", "telegram-file", now=now,
        )

    assert result == "shifts/2026/05/09/7_end_140000.jpg"
    assert sent_url["url"] == (
        "https://example.supabase.co/storage/v1/object/shift-photos/"
        "shifts/2026/05/09/7_end_140000.jpg"
    )
    assert sent_url["body"] == "fake-bytes"


@pytest.mark.asyncio
async def test_archive_swallows_upload_failure() -> None:
    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="p.jpg"))

    async def fake_download(_p: str, destination: object) -> None:
        destination.write(b"x")  # type: ignore[attr-defined]

    bot.download_file = AsyncMock(side_effect=fake_download)

    class BoomClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "BoomClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(self, *args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("boom")

    with patch.object(httpx, "AsyncClient", BoomClient):
        result = await archive_shift_photo(
            bot, _settings(enabled=True), 1, "start", "fid",
        )
    assert result is None
