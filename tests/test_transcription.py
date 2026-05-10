"""Tests for the OpenAI Whisper transcription service."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from src.core.config import Settings
from src.services.transcription import (
    transcribe_voice,
    transcription_enabled,
)


def _settings(enabled: bool = True) -> Settings:
    return Settings(  # type: ignore[call-arg]
        bot_token="x",
        owner_tg_id=1,
        openai_api_key="sk-test" if enabled else "",
    )


def test_transcription_enabled_requires_key() -> None:
    assert transcription_enabled(_settings(enabled=True)) is True
    assert transcription_enabled(_settings(enabled=False)) is False


@pytest.mark.asyncio
async def test_transcribe_returns_none_when_disabled() -> None:
    bot = MagicMock()
    result = await transcribe_voice(bot, _settings(enabled=False), "fid")
    assert result is None


@pytest.mark.asyncio
async def test_transcribe_calls_whisper_and_returns_text() -> None:
    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="voice/abc.ogg"))

    async def fake_download(_path: str, destination: object) -> None:
        destination.write(b"audio-bytes")  # type: ignore[attr-defined]

    bot.download_file = AsyncMock(side_effect=fake_download)

    captured: dict[str, object] = {}

    class FakeResponse:
        text = "  расшифрованный текст  "

        def raise_for_status(self) -> None:
            return None

    class FakeClient:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "FakeClient":
            return self

        async def __aexit__(self, *exc: object) -> None:
            return None

        async def post(
            self,
            url: str,
            *,
            headers: dict[str, str],
            data: dict[str, str],
            files: dict[str, object],
        ) -> FakeResponse:
            captured["url"] = url
            captured["headers"] = headers
            captured["data"] = data
            captured["files"] = files
            return FakeResponse()

    with patch.object(httpx, "AsyncClient", FakeClient):
        result = await transcribe_voice(bot, _settings(enabled=True), "fid")

    assert result == "расшифрованный текст"
    assert captured["url"] == "https://api.openai.com/v1/audio/transcriptions"
    assert captured["headers"] == {"Authorization": "Bearer sk-test"}
    data = captured["data"]
    assert isinstance(data, dict)
    assert data["model"] == "whisper-1"
    assert data["language"] == "ru"
    assert data["response_format"] == "text"


@pytest.mark.asyncio
async def test_transcribe_swallows_http_errors() -> None:
    bot = MagicMock()
    bot.get_file = AsyncMock(return_value=MagicMock(file_path="voice/abc.ogg"))

    async def fake_download(_path: str, destination: object) -> None:
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
        result = await transcribe_voice(bot, _settings(enabled=True), "fid")
    assert result is None
