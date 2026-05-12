"""Phase 6.11a..d: ``/report`` — rolling N-month summary.

Single-user accounting bot's "where do I stand overall?" view. Default
window is the last 6 months; ``/report N`` picks any 1..24-month window.
``/period`` remains the single-month deep-dive; this command is the
roll-up. The text response carries «📥 XLSX» + «📄 PDF» + «📈 PNG»
inline buttons that re-fetch and ship the same window as a downloadable
file.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import structlog
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
from src.core.db_metrics import count_queries
from src.core.models import User
from src.services.reports.archive import archive_filename, build_report_archive
from src.services.reports.pdf import build_report_pdf, pdf_filename
from src.services.reports.png import build_report_png, png_filename
from src.services.reports.service import get_report_data
from src.services.reports.text import format_report_text
from src.services.reports.xlsx import build_report_xlsx, xlsx_filename

logger = structlog.get_logger()

router = Router()

DEFAULT_MONTHS = 6
MIN_MONTHS = 1
MAX_MONTHS = 24

_XLSX_CB_PREFIX = "report:xlsx:"
_PDF_CB_PREFIX = "report:pdf:"
_PNG_CB_PREFIX = "report:png:"
_RUN_CB_PREFIX = "report:run:"
_PERIOD_PNG_CB_PREFIX = "period:png:"  # PNG for a single (year, month)

_MENU_WINDOWS: tuple[int, ...] = (3, 6, 12, 24)


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


def period_png_keyboard(year: int, month: int) -> InlineKeyboardMarkup:
    """Single-button keyboard offering a PNG chart for ``(year, month)``."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("period_btn_png"),
                    callback_data=f"{_PERIOD_PNG_CB_PREFIX}{year}-{month:02d}",
                ),
            ],
        ],
    )


def report_menu_keyboard() -> InlineKeyboardMarkup:
    """Inline picker shown when the «📊 Отчёты» button is tapped."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t(f"report_menu_{m}m"),
                    callback_data=f"{_RUN_CB_PREFIX}{m}",
                )
                for m in _MENU_WINDOWS
            ],
        ],
    )


def _download_keyboard(months: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("report_btn_xlsx"),
                    callback_data=f"{_XLSX_CB_PREFIX}{months}",
                ),
                InlineKeyboardButton(
                    text=t("report_btn_pdf"),
                    callback_data=f"{_PDF_CB_PREFIX}{months}",
                ),
                InlineKeyboardButton(
                    text=t("report_btn_png"),
                    callback_data=f"{_PNG_CB_PREFIX}{months}",
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
    with count_queries() as q:
        async for session in get_session():
            data = await get_report_data(
                session, user=db_user, tz=tz, today=today, months=months,
            )
    logger.info(
        "report_query_count",
        user_id=db_user.id, months=months, queries=q.count,
    )
    await message.answer(
        format_report_text(data, db_user),
        reply_markup=_download_keyboard(months),
    )


async def _send_report_file(
    callback: CallbackQuery, db_user: User, prefix: str,
    builder, filename_fn,  # noqa: ANN001
) -> None:
    if callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        months = int(callback.data[len(prefix):])
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

    buf = builder(data, db_user)
    document = BufferedInputFile(buf.getvalue(), filename=filename_fn(months))
    await callback.message.answer_document(document)
    await callback.answer()


@router.callback_query(lambda cq: (cq.data or "").startswith(_XLSX_CB_PREFIX))
async def cb_report_xlsx(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    await _send_report_file(
        callback, db_user, _XLSX_CB_PREFIX, build_report_xlsx, xlsx_filename,
    )


@router.callback_query(lambda cq: (cq.data or "").startswith(_PDF_CB_PREFIX))
async def cb_report_pdf(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    await _send_report_file(
        callback, db_user, _PDF_CB_PREFIX, build_report_pdf, pdf_filename,
    )


@router.callback_query(lambda cq: (cq.data or "").startswith(_PNG_CB_PREFIX))
async def cb_report_png(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    await _send_report_file(
        callback, db_user, _PNG_CB_PREFIX, build_report_png, png_filename,
    )


@router.message(Command("export_archive"))
async def cmd_export_archive(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Bundle XLSX + PDF + PNG for the requested window into a single ZIP."""
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
    buf = build_report_archive(data, db_user, months)
    document = BufferedInputFile(buf.getvalue(), filename=archive_filename(months))
    await message.answer_document(
        document, caption=t("archive_caption", months=months),
    )


@router.callback_query(
    lambda cq: (cq.data or "").startswith(_PERIOD_PNG_CB_PREFIX),
)
async def cb_period_png(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    """Build a single-month PNG anchored at the requested (year, month)."""
    if db_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    arg = callback.data[len(_PERIOD_PNG_CB_PREFIX):]
    try:
        year = int(arg[:4])
        month = int(arg[5:7])
    except (ValueError, IndexError):
        await callback.answer()
        return
    if not (1 <= month <= 12):
        await callback.answer()
        return

    from src.services.advances import month_bounds

    _, last_day = month_bounds(year, month)
    tz = ZoneInfo(get_settings().timezone)
    async for session in get_session():
        data = await get_report_data(
            session, user=db_user, tz=tz, today=last_day, months=1,
        )
    buf = build_report_png(data, db_user)
    document = BufferedInputFile(
        buf.getvalue(), filename=f"period_{year}-{month:02d}.png",
    )
    await callback.message.answer_document(document)
    await callback.answer()


@router.callback_query(lambda cq: (cq.data or "").startswith(_RUN_CB_PREFIX))
async def cb_report_run(
    callback: CallbackQuery, db_user: User | None = None,
) -> None:
    """Render the text report for the window picked from the inline menu."""
    if db_user is None or callback.data is None or callback.message is None:
        await callback.answer()
        return
    try:
        months = int(callback.data[len(_RUN_CB_PREFIX):])
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
    await callback.message.answer(
        format_report_text(data, db_user),
        reply_markup=_download_keyboard(months),
    )
    await callback.answer()
