"""Voice transcription via OpenAI Whisper API.

Used to convert Telegram voice messages into shift notes. Transcription is
opt-in via OPENAI_API_KEY env var; when disabled, callers should fall back
silently. Failures are logged and surfaced as None — never raised — so a
network blip does not interrupt the shift flow.
"""

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

import httpx
import structlog

if TYPE_CHECKING:
    from aiogram import Bot

    from src.core.config import Settings

logger = structlog.get_logger()

_API_URL = "https://api.openai.com/v1/audio/transcriptions"


def transcription_enabled(settings: Settings) -> bool:
    return bool(settings.openai_api_key)


async def _download_telegram_file(bot: Bot, file_id: str) -> bytes:
    file = await bot.get_file(file_id)
    if file.file_path is None:
        raise RuntimeError("telegram file has no path")
    buffer = BytesIO()
    await bot.download_file(file.file_path, destination=buffer)
    return buffer.getvalue()


async def _post_to_whisper(
    settings: Settings, audio_bytes: bytes, filename: str,
) -> str | None:
    headers = {"Authorization": f"Bearer {settings.openai_api_key}"}
    data: dict[str, str] = {
        "model": settings.whisper_model,
        "response_format": "text",
    }
    if settings.whisper_language:
        data["language"] = settings.whisper_language
    files = {"file": (filename, audio_bytes, "audio/ogg")}
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            _API_URL, headers=headers, data=data, files=files,
        )
    response.raise_for_status()
    return response.text.strip() or None


async def transcribe_voice(
    bot: Bot, settings: Settings, file_id: str,
) -> str | None:
    """Download a Telegram voice file and run it through Whisper.

    Returns the transcribed text, or None if disabled / on any error.
    """
    if not transcription_enabled(settings):
        return None
    try:
        audio = await _download_telegram_file(bot, file_id)
        return await _post_to_whisper(settings, audio, f"{file_id}.ogg")
    except (httpx.HTTPError, RuntimeError, OSError) as exc:
        logger.warning("voice_transcription_failed", error=str(exc)[:200])
        return None
