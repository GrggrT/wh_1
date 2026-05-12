"""Phase 6.11a/6.11b: ``/report`` — rolling N-month summary.

Single-user accounting bot's "where do I stand overall?" view. Default
window is the last 6 months; ``/report N`` picks any 1..24-month window.
``/period`` remains the single-month deep-dive; this command is the
roll-up. Phase 6.11b adds an inline «📥 Скачать XLSX» button that
re-fetches and ships the same window as a workbook.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.reports.service import get_report_data
from src.services.reports.text import format_report_text
from src.services.reports.xlsx import build_report_xlsx, xlsx_filename

router = Router()

DEFAULT_MONTHS = 6
MIN_MONTHS = 1
MAX_MONTHS = 24

_XLSX_CB_PREFIX = "report:xlsx:"


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


def _xlsx_keyboard(months: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("report_btn_xlsx"),
                    callback_data=f"{_XLSX_CB_PREFIX}{months}",
                ),
            ],
        ],
    )


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
    await message.answer(
        format_report_text(data, db_user),
        reply_markup=_xlsx_keyboard(months),
    )


@router.callback_query(lambda cq: (cq.data or "").startswith(_XLSX_CB_PREFIX))
async def cb_report_xlsx(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        months = int(callback.data[len(_XLSX_CB_PREFIX):])
    except ValueError:
        await callback.answer()
        return
    if not (MIN_MONTHS <= months <= MAX_MONTHS):
        await callback.answer()
        return

    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    async for session in get_session():
        data = await get_report_data(
            session, user=db_user, tz=tz, today=today, months=months,
        )

    buf = build_report_xlsx(data, db_user)
    document = BufferedInputFile(buf.getvalue(), filename=xlsx_filename(months))
    await callback.message.answer_document(document)
    await callback.answer()
