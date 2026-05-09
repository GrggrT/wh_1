"""Background task that periodically auto-closes long shifts and sends reminders."""

import asyncio
from decimal import Decimal

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from src.bot.strings import t
from src.core.config import Settings
from src.core.db import get_session
from src.services.reports import compute_hours
from src.services.scheduler import (
    auto_close_shift,
    find_long_open_shifts,
    find_shifts_needing_reminder,
    get_user_tg_id,
    mark_reminder_sent,
)

logger = structlog.get_logger()


async def _process_once(bot: Bot, settings: Settings) -> None:
    async for session in get_session():
        # Reminders
        reminder_shifts = await find_shifts_needing_reminder(
            session,
            threshold_hours=settings.reminder_after_hours,
            max_hours=settings.max_shift_hours,
        )
        for shift in reminder_shifts:
            tg_id = await get_user_tg_id(session, shift.user_id)
            await mark_reminder_sent(session, shift)
            if tg_id is None:
                continue
            try:
                hours_open = compute_hours(
                    shift.start_at,
                    shift.start_at.__class__.now(tz=shift.start_at.tzinfo),
                ).quantize(Decimal("0.1"))
                await bot.send_message(
                    tg_id,
                    t("shift_reminder", hours=str(hours_open)),
                )
            except TelegramAPIError:
                logger.warning("reminder_send_failed", shift_id=shift.id)

        # Auto close
        long_shifts = await find_long_open_shifts(
            session, max_hours=settings.max_shift_hours,
        )
        for shift in long_shifts:
            tg_id = await get_user_tg_id(session, shift.user_id)
            await auto_close_shift(session, shift)
            if tg_id is None:
                continue
            try:
                hours = compute_hours(
                    shift.start_at,
                    shift.end_at,  # type: ignore[arg-type]
                ).quantize(Decimal("0.01"))
                await bot.send_message(
                    tg_id,
                    t("shift_auto_closed", hours=str(hours)),
                )
            except TelegramAPIError:
                logger.warning("auto_close_notify_failed", shift_id=shift.id)

        await session.commit()


async def run_scheduler(bot: Bot, settings: Settings) -> None:
    """Run the maintenance loop until cancelled."""
    interval = settings.scheduler_interval_seconds
    logger.info("scheduler_starting", interval_seconds=interval)
    while True:
        try:
            await _process_once(bot, settings)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler_iteration_failed")
        await asyncio.sleep(interval)
