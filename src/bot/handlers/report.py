"""Phase 6.11a: ``/report`` — rolling N-month summary.

Single-user accounting bot's "where do I stand overall?" view. Default
window is the last 6 months; ``/report N`` picks any 1..24-month window.
``/period`` remains the single-month deep-dive; this command is the
roll-up.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.reports.service import get_report_data
from src.services.reports.text import format_report_text

router = Router()

DEFAULT_MONTHS = 6
MIN_MONTHS = 1
MAX_MONTHS = 24


def parse_months_arg(raw: str | None) -> int | None:
    """Parse the optional ``N`` arg. Returns ``None`` on bad input."""
    if raw is None:
        return DEFAULT_MONTHS
    s = raw.strip()
    if not s:
        return DEFAULT_MONTHS
    try:
        n = int(s)
    except ValueError:
        return None
    if not (MIN_MONTHS <= n <= MAX_MONTHS):
        return None
    return n


@router.message(Command("report"))
async def cmd_report(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    months = parse_months_arg(command.args)
    if months is None:
        await message.answer(t("report_bad_arg"))
        return
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    async for session in get_session():
        data = await get_report_data(
            session, user=db_user, tz=tz, today=today, months=months,
        )
    await message.answer(format_report_text(data, db_user))
