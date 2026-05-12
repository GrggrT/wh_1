"""Phase 7.1: ``/backup`` — full XLSX export of the user's accounting data.

Exports profile + day_entries + advances + salary_payments into a single
workbook. Useful as a personal safety net before product changes or
account deletion.

Phase 7.1b: ``/restore`` — companion inverse, ingesting a previously
emitted backup workbook back into the calling user's tables. Duplicate
rows (matching natural keys) are skipped, never overwritten.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy import select

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Advance, DayEntry, SalaryPayment, User
from src.services.reports.backup import backup_filename, build_backup_xlsx
from src.services.reports.restore import (
    BackupParseError,
    apply_restore,
    parse_backup_xlsx,
)
from src.services.share_backup import (
    ShareTokenError,
    issue_share_token,
    redeem_share_token,
)

logger = structlog.get_logger()

router = Router()


class RestoreFlow(StatesGroup):
    awaiting_document = State()
    awaiting_confirm = State()


@router.message(Command("backup"))
async def cmd_backup(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    async for session in get_session():
        days = (
            await session.execute(
                select(DayEntry)
                .where(DayEntry.user_id == db_user.id)
                .order_by(DayEntry.day),
            )
        ).scalars().all()
        advs = (
            await session.execute(
                select(Advance)
                .where(Advance.user_id == db_user.id)
                .order_by(Advance.day),
            )
        ).scalars().all()
        pays = (
            await session.execute(
                select(SalaryPayment)
                .where(SalaryPayment.user_id == db_user.id)
                .order_by(SalaryPayment.paid_on),
            )
        ).scalars().all()

    buf = build_backup_xlsx(
        db_user, list(days), list(advs), list(pays), today=today,
    )
    document = BufferedInputFile(
        buf.getvalue(), filename=backup_filename(db_user, today),
    )
    await message.answer_document(
        document,
        caption=t(
            "backup_caption",
            days=len(days),
            advances=len(advs),
            payments=len(pays),
        ),
    )


_MAX_BACKUP_BYTES = 5 * 1024 * 1024  # 5 MB is plenty for an accounting XLSX.


@router.message(Command("restore"))
async def cmd_restore(message: Message, state: FSMContext) -> None:
    await state.set_state(RestoreFlow.awaiting_document)
    await message.answer(t("restore_prompt"))


@router.message(RestoreFlow.awaiting_document, Command("cancel"))
@router.message(RestoreFlow.awaiting_confirm, Command("cancel"))
async def cmd_restore_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("cancelled"))


def _restore_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=t("restore_btn_confirm"), callback_data="restore:apply",
            ),
            InlineKeyboardButton(
                text=t("restore_btn_cancel"), callback_data="restore:cancel",
            ),
        ]],
    )


@router.message(RestoreFlow.awaiting_document, F.document)
async def msg_restore_document(
    message: Message,
    state: FSMContext,
    bot: Bot,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    document = message.document
    if document is None:
        return
    name = (document.file_name or "").lower()
    if not name.endswith(".xlsx"):
        await message.answer(t("restore_bad_format"))
        return
    if document.file_size and document.file_size > _MAX_BACKUP_BYTES:
        await message.answer(t("restore_too_large"))
        return

    buf = BytesIO()
    file = await bot.get_file(document.file_id)
    if file.file_path is None:
        await message.answer(t("restore_failed", error="no file path"))
        return
    await bot.download_file(file.file_path, destination=buf)
    buf.seek(0)

    try:
        plan = parse_backup_xlsx(buf)
    except BackupParseError as exc:
        await message.answer(t("restore_failed", error=str(exc)))
        with contextlib.suppress(Exception):
            await state.clear()
        return

    await state.update_data(file_id=document.file_id)
    await state.set_state(RestoreFlow.awaiting_confirm)
    await message.answer(
        t(
            "restore_preview",
            days=len(plan.days),
            advances=len(plan.advances),
            payments=len(plan.payments),
        ),
        reply_markup=_restore_confirm_kb(),
    )


@router.callback_query(RestoreFlow.awaiting_confirm, F.data == "restore:cancel")
async def cb_restore_cancel(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t("restore_cancelled"))
    await callback.answer()


@router.callback_query(RestoreFlow.awaiting_confirm, F.data == "restore:apply")
async def cb_restore_apply(
    callback: CallbackQuery,
    state: FSMContext,
    bot: Bot,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    data = await state.get_data()
    file_id = data.get("file_id")
    if not file_id or not isinstance(callback.message, Message):
        await state.clear()
        await callback.answer()
        return

    buf = BytesIO()
    file = await bot.get_file(file_id)
    if file.file_path is None:
        await callback.message.answer(t("restore_failed", error="no file path"))
        await state.clear()
        await callback.answer()
        return
    await bot.download_file(file.file_path, destination=buf)
    buf.seek(0)

    try:
        plan = parse_backup_xlsx(buf)
    except BackupParseError as exc:
        await callback.message.answer(t("restore_failed", error=str(exc)))
        await state.clear()
        await callback.answer()
        return

    async for session in get_session():
        result = await apply_restore(session, user=db_user, plan=plan)
        await session.commit()

    logger.info(
        "restore_applied",
        user_id=db_user.id,
        tg_id=db_user.tg_id,
        days_inserted=result.days_inserted,
        days_skipped=result.days_skipped,
        advances_inserted=result.advances_inserted,
        advances_skipped=result.advances_skipped,
        payments_inserted=result.payments_inserted,
        payments_skipped=result.payments_skipped,
    )

    await state.clear()
    with contextlib.suppress(Exception):
        await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        t(
            "restore_done",
            days_in=result.days_inserted, days_skip=result.days_skipped,
            adv_in=result.advances_inserted, adv_skip=result.advances_skipped,
            pay_in=result.payments_inserted, pay_skip=result.payments_skipped,
        ),
    )
    await callback.answer()


@router.message(RestoreFlow.awaiting_document)
async def msg_restore_other(message: Message) -> None:
    await message.answer(t("restore_need_document"))


@router.message(RestoreFlow.awaiting_confirm)
async def msg_restore_awaiting_confirm(message: Message) -> None:
    await message.answer(
        t("restore_btn_confirm") + " / " + t("restore_btn_cancel"),
        reply_markup=_restore_confirm_kb(),
    )


@router.message(Command("share_backup"))
async def cmd_share_backup(
    message: Message, db_user: User | None = None,
) -> None:
    """Mint a one-shot token a different Telegram account can redeem."""
    if db_user is None:
        return
    async for session in get_session():
        issued = await issue_share_token(session, source_user=db_user)
        await session.commit()
    logger.info(
        "share_backup_issued",
        user_id=db_user.id,
        tg_id=db_user.tg_id,
        expires_at=issued.expires_at.isoformat(),
    )
    await message.answer(
        t(
            "share_backup_issued",
            token=issued.token,
            expires=issued.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
        ),
    )


@router.message(Command("restore_from"))
async def cmd_restore_from(
    message: Message,
    command: CommandObject,
    db_user: User | None = None,
) -> None:
    """Redeem a share token issued by another account."""
    if db_user is None:
        return
    token = (command.args or "").strip()
    if not token:
        await message.answer(t("restore_from_usage"))
        return
    async for session in get_session():
        try:
            result = await redeem_share_token(
                session, token=token, redeemer=db_user,
            )
        except ShareTokenError as exc:
            await session.rollback()
            await message.answer(t("restore_from_failed", reason=str(exc)))
            return
        await session.commit()
    logger.info(
        "share_backup_redeemed",
        redeemer_user_id=db_user.id,
        redeemer_tg_id=db_user.tg_id,
        days_inserted=result.days_inserted,
        days_skipped=result.days_skipped,
        advances_inserted=result.advances_inserted,
        advances_skipped=result.advances_skipped,
        payments_inserted=result.payments_inserted,
        payments_skipped=result.payments_skipped,
    )
    await message.answer(
        t(
            "restore_done",
            days_in=result.days_inserted, days_skip=result.days_skipped,
            adv_in=result.advances_inserted, adv_skip=result.advances_skipped,
            pay_in=result.payments_inserted, pay_skip=result.payments_skipped,
        ),
    )
