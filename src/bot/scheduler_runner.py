"""Background task that periodically auto-closes long shifts and sends reminders."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from src.bot.strings import t
from src.core.config import Settings
from src.core.db import get_session
from src.services.breaks import auto_close_break, find_stale_open_breaks
from src.services.digest import (
    build_daily_digest,
    build_monthly_digest,
    build_weekly_digest,
    previous_full_week,
    previous_month,
)
from src.services.reports import compute_hours
from src.services.scheduler import (
    auto_close_shift,
    find_long_open_shifts,
    find_shifts_needing_reminder,
    get_user_tg_id,
    mark_reminder_sent,
)

logger = structlog.get_logger()


_last_digest_date: date | None = None
_last_monthly_digest_period: tuple[int, int] | None = None
_last_weekly_digest_iso_week: tuple[int, int] | None = None


async def _process_once(bot: Bot, settings: Settings) -> None:
    async for session in get_session():
        # Stale break auto-close (notify the affected user)
        stale_breaks = await find_stale_open_breaks(
            session, max_break_hours=settings.max_break_hours,
        )
        for br in stale_breaks:
            from sqlalchemy import select as _select

            from src.core.models import Shift as _Shift

            shift_obj = (
                await session.execute(_select(_Shift).where(_Shift.id == br.shift_id))
            ).scalar_one_or_none()
            await auto_close_break(session, br)
            if shift_obj is None:
                continue
            tg_id = await get_user_tg_id(session, shift_obj.user_id)
            if tg_id is None:
                continue
            try:
                minutes_open = int(
                    (br.end_at - br.start_at).total_seconds() // 60,  # type: ignore[operator]
                )
                await bot.send_message(
                    tg_id,
                    t("break_auto_closed", minutes=minutes_open),
                )
            except TelegramAPIError:
                logger.warning("break_auto_close_notify_failed", break_id=br.id)

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


async def _maybe_send_daily_digest(bot: Bot, settings: Settings) -> None:
    """Once per day after the configured local hour, DM the owner a summary."""
    global _last_digest_date
    if not settings.daily_digest_enabled:
        return
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz=tz)
    today = now_local.date()
    if _last_digest_date == today:
        return
    if now_local.hour < settings.daily_digest_hour:
        return
    body = ""
    async for session in get_session():
        body = await build_daily_digest(session, tz, now_local)
    try:
        await bot.send_message(settings.owner_tg_id, body)
        _last_digest_date = today
    except TelegramAPIError:
        logger.warning("daily_digest_send_failed")


async def _maybe_send_monthly_digest(bot: Bot, settings: Settings) -> None:
    """On day 1 after the configured hour, DM the owner the previous month summary."""
    global _last_monthly_digest_period
    if not settings.daily_digest_enabled:
        return
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz=tz)
    if now_local.day != 1:
        return
    if now_local.hour < settings.daily_digest_hour:
        return
    prev_year, prev_month = previous_month(now_local.year, now_local.month)
    period_key = (prev_year, prev_month)
    if _last_monthly_digest_period == period_key:
        return
    body = ""
    async for session in get_session():
        body = await build_monthly_digest(session, tz, prev_year, prev_month)
    try:
        await bot.send_message(settings.owner_tg_id, body)
        _last_monthly_digest_period = period_key
    except TelegramAPIError:
        logger.warning("monthly_digest_send_failed")


async def _maybe_send_weekly_digest(bot: Bot, settings: Settings) -> None:
    """On Monday after the configured hour, DM the owner the prior-week summary."""
    global _last_weekly_digest_iso_week
    if not settings.daily_digest_enabled:
        return
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz=tz)
    if now_local.weekday() != 0:  # Monday only
        return
    if now_local.hour < settings.daily_digest_hour:
        return
    week_start, week_end = previous_full_week(now_local.date())
    iso_year, iso_week, _ = week_start.isocalendar()
    iso_key = (iso_year, iso_week)
    if _last_weekly_digest_iso_week == iso_key:
        return
    body = ""
    async for session in get_session():
        body = await build_weekly_digest(session, tz, week_start, week_end)
    try:
        await bot.send_message(settings.owner_tg_id, body)
        _last_weekly_digest_iso_week = iso_key
    except TelegramAPIError:
        logger.warning("weekly_digest_send_failed")


async def run_scheduler(bot: Bot, settings: Settings) -> None:
    """Run the maintenance loop until cancelled."""
    interval = settings.scheduler_interval_seconds
    logger.info("scheduler_starting", interval_seconds=interval)
    while True:
        try:
            await _process_once(bot, settings)
            await _maybe_send_daily_digest(bot, settings)
            await _maybe_send_weekly_digest(bot, settings)
            await _maybe_send_monthly_digest(bot, settings)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler_iteration_failed")
        await asyncio.sleep(interval)
