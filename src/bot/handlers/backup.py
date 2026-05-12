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
from src.services.backup_cloud import (
    CloudBackupError,
    cloud_storage_enabled,
    fetch_cloud_backup,
    register_cloud_backup,
)
from src.services.reports.backup import backup_filename, build_backup_xlsx
from src.services.reports.restore import (
    BackupParseError,
    apply_restore,
    parse_backup_xlsx,
)
from src.services.share_backup import (
    ShareTokenError,
    issue_share_token,
    peek_share_token,
    redeem_share_token,
)

logger = structlog.get_logger()

router = Router()


class RestoreFlow(StatesGroup):
    awaiting_document = State()
    awaiting_confirm = State()


class ShareRestoreFlow(StatesGroup):
    awaiting_confirm = State()


class CloudRestoreFlow(StatesGroup):
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


@router.message(Command("backup_to_cloud"))
async def cmd_backup_to_cloud(
    message: Message, db_user: User | None = None,
) -> None:
    """Build a backup XLSX and stash it in object storage; return a key."""
    if db_user is None:
        return
    settings = get_settings()
    if not cloud_storage_enabled(settings):
        await message.answer(t("cloud_backup_disabled"))
        return
    tz = ZoneInfo(settings.timezone)
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
        data = buf.getvalue()
        try:
            issued = await register_cloud_backup(
                session, owner=db_user, data=data, settings=settings,
            )
        except CloudBackupError as exc:
            await session.rollback()
            await message.answer(
                t("cloud_backup_failed", reason=str(exc)),
            )
            return
        await session.commit()
    logger.info(
        "cloud_backup_uploaded",
        user_id=db_user.id, tg_id=db_user.tg_id,
        size_bytes=issued.size_bytes,
    )
    await message.answer(
        t(
            "cloud_backup_uploaded",
            key=issued.key,
            expires=issued.expires_at.strftime("%Y-%m-%d %H:%M UTC"),
            size_kb=round(issued.size_bytes / 1024, 1),
        ),
    )


def _share_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=t("restore_btn_confirm"), callback_data="share:apply",
            ),
            InlineKeyboardButton(
                text=t("restore_btn_cancel"), callback_data="share:cancel",
            ),
        ]],
    )


def _cloud_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text=t("restore_btn_confirm"), callback_data="cloud:apply",
            ),
            InlineKeyboardButton(
                text=t("restore_btn_cancel"), callback_data="cloud:cancel",
            ),
        ]],
    )


@router.message(ShareRestoreFlow.awaiting_confirm, Command("cancel"))
@router.message(CloudRestoreFlow.awaiting_confirm, Command("cancel"))
async def cmd_share_or_cloud_cancel(
    message: Message, state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(t("cancelled"))


@router.message(Command("restore_from_cloud"))
async def cmd_restore_from_cloud(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    """Fetch a cloud-stashed backup, preview row counts, await confirmation."""
    if db_user is None:
        return
    key = (command.args or "").strip()
    if not key:
        await message.answer(t("restore_from_cloud_usage"))
        return
    settings = get_settings()
    if not cloud_storage_enabled(settings):
        await message.answer(t("cloud_backup_disabled"))
        return
    async for session in get_session():
        try:
            raw = await fetch_cloud_backup(
                session, key=key, settings=settings,
            )
        except CloudBackupError as exc:
            await message.answer(
                t("restore_from_cloud_failed", reason=str(exc)),
            )
            return
    try:
        plan = parse_backup_xlsx(BytesIO(raw))
    except BackupParseError as exc:
        await message.answer(t("restore_failed", error=str(exc)))
        return

    await state.update_data(cloud_key=key)
    await state.set_state(CloudRestoreFlow.awaiting_confirm)
    await message.answer(
        t(
            "restore_from_cloud_preview",
            days=len(plan.days),
            advances=len(plan.advances),
            payments=len(plan.payments),
        ),
        reply_markup=_cloud_confirm_kb(),
    )


@router.callback_query(
    CloudRestoreFlow.awaiting_confirm, F.data == "cloud:cancel",
)
async def cb_cloud_cancel(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t("restore_cancelled"))
    await callback.answer()


@router.callback_query(
    CloudRestoreFlow.awaiting_confirm, F.data == "cloud:apply",
)
async def cb_cloud_apply(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    data = await state.get_data()
    key = data.get("cloud_key")
    if not key or not isinstance(callback.message, Message):
        await state.clear()
        await callback.answer()
        return
    settings = get_settings()
    if not cloud_storage_enabled(settings):
        await state.clear()
        await callback.message.answer(t("cloud_backup_disabled"))
        await callback.answer()
        return

    async for session in get_session():
        try:
            raw = await fetch_cloud_backup(
                session, key=key, settings=settings,
            )
        except CloudBackupError as exc:
            await callback.message.answer(
                t("restore_from_cloud_failed", reason=str(exc)),
            )
            await state.clear()
            await callback.answer()
            return
        try:
            plan = parse_backup_xlsx(BytesIO(raw))
        except BackupParseError as exc:
            await callback.message.answer(t("restore_failed", error=str(exc)))
            await state.clear()
            await callback.answer()
            return
        result = await apply_restore(session, user=db_user, plan=plan)
        await session.commit()

    logger.info(
        "cloud_backup_restored",
        user_id=db_user.id, tg_id=db_user.tg_id,
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


@router.message(Command("restore_from"))
async def cmd_restore_from(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    """Peek a share token, preview row counts, await confirmation."""
    if db_user is None:
        return
    token = (command.args or "").strip()
    if not token:
        await message.answer(t("restore_from_usage"))
        return
    async for session in get_session():
        try:
            plan = await peek_share_token(
                session, token=token, redeemer=db_user,
            )
        except ShareTokenError as exc:
            await message.answer(t("restore_from_failed", reason=str(exc)))
            return
        # Peek is read-only; no commit required.

    await state.update_data(share_token=token)
    await state.set_state(ShareRestoreFlow.awaiting_confirm)
    await message.answer(
        t(
            "restore_from_preview",
            days=len(plan.days),
            advances=len(plan.advances),
            payments=len(plan.payments),
        ),
        reply_markup=_share_confirm_kb(),
    )


@router.callback_query(
    ShareRestoreFlow.awaiting_confirm, F.data == "share:cancel",
)
async def cb_share_cancel(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(t("restore_cancelled"))
    await callback.answer()


@router.callback_query(
    ShareRestoreFlow.awaiting_confirm, F.data == "share:apply",
)
async def cb_share_apply(
    callback: CallbackQuery,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None:
        await callback.answer()
        return
    data = await state.get_data()
    token = data.get("share_token")
    if not token or not isinstance(callback.message, Message):
        await state.clear()
        await callback.answer()
        return

    async for session in get_session():
        try:
            result = await redeem_share_token(
                session, token=token, redeemer=db_user,
            )
        except ShareTokenError as exc:
            await session.rollback()
            await callback.message.answer(
                t("restore_from_failed", reason=str(exc)),
            )
            await state.clear()
            await callback.answer()
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
