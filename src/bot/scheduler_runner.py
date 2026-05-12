"""Background task that periodically auto-closes long shifts and sends reminders."""

import asyncio
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from sqlalchemy import select

from src.bot.handlers.day_entries import quick_keyboard
from src.bot.strings import t
from src.core.config import Settings
from src.core.db import get_session
from src.core.models import User
from src.services.breaks import auto_close_break, find_stale_open_breaks
from src.services.day_entries import (
    format_hours,
    list_recent_entries,
    quick_pick_values,
    smart_suggest,
)
from src.services.digest import (
    build_daily_digest,
    build_monthly_digest,
    build_weekly_digest,
    previous_full_week,
    previous_month,
)
from src.services.reminders import find_users_needing_reminder, mark_reminded
from src.services.reminders_smart import aged_open_periods, users_with_gap
from src.services.reports import compute_hours
from src.services.reports.png import build_report_png
from src.services.reports.service import get_report_data
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
# Phase 7.2: in-memory per-user state for the smart reminders. Single-tenant
# bot, so a process-local dict is sufficient; a deploy restart at worst
# resends one nudge.
_last_gap_nudge_by_user: dict[int, date] = {}
_last_debt_ping_iso_week_by_user: dict[int, tuple[int, int]] = {}

_RU_MONTHS_SCH: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


def _now_local(tz: ZoneInfo) -> datetime:
    """Indirection so tests can freeze time without touching datetime globally."""
    return datetime.now(tz=tz)


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
    """On day 1 after the configured hour, DM the owner the previous month summary.

    Phase 7.5: also attaches a single-month PNG chart of the prior period
    so the owner can eyeball «начислено vs получено» at a glance. PNG
    generation is best-effort — if anything goes wrong (no data, matplotlib
    error) we still deliver the text digest.
    """
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
    owner_user: User | None = None
    png_bytes: bytes | None = None
    async for session in get_session():
        body = await build_monthly_digest(session, tz, prev_year, prev_month)
        owner_user = (
            await session.execute(
                select(User).where(User.tg_id == settings.owner_tg_id),
            )
        ).scalar_one_or_none()
        if owner_user is not None:
            try:
                from datetime import date as _date

                anchor = _date(prev_year, prev_month, 1)
                data = await get_report_data(
                    session, user=owner_user, tz=tz, today=anchor, months=1,
                )
                png_bytes = build_report_png(data, owner_user).getvalue()
            except Exception:  # noqa: BLE001 — PNG is best-effort
                logger.warning("monthly_digest_png_failed", exc_info=True)
    try:
        await bot.send_message(settings.owner_tg_id, body)
        if png_bytes is not None:
            from aiogram.types import BufferedInputFile

            filename = f"report_{prev_year:04d}-{prev_month:02d}.png"
            await bot.send_document(
                settings.owner_tg_id,
                BufferedInputFile(png_bytes, filename=filename),
            )
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


async def _maybe_send_day_reminders(bot: Bot, settings: Settings) -> None:
    """DM each user with the inline quick-pick at/after their configured
    local reminder hour, once per day, only when no day-entry exists yet."""
    tz = ZoneInfo(settings.timezone)
    now_local = datetime.now(tz=tz)
    today = now_local.date()
    async for session in get_session():
        users = await find_users_needing_reminder(session, tz=tz, now=now_local)
        if not users:
            return
        for user in users:
            recent = await list_recent_entries(session, user_id=user.id, days=14)
            suggested = smart_suggest(recent)
            picks = quick_pick_values(suggested)
            text = (
                t("day_reminder_with_suggest", suggest=format_hours(suggested))
                if suggested is not None
                else t("day_reminder_text")
            )
            try:
                await bot.send_message(
                    user.tg_id, text, reply_markup=quick_keyboard(picks),
                )
            except TelegramAPIError:
                logger.warning("day_reminder_send_failed", user_id=user.id)
                continue
            await mark_reminded(session, user=user, today=today)
        await session.commit()


async def _maybe_send_gap_nudges(bot: Bot, settings: Settings) -> None:
    """Once per day, after the daily-reminder hour, nudge users who haven't
    logged hours in 3+ business days. Skips users already nudged today.
    """
    tz = ZoneInfo(settings.timezone)
    now_local = _now_local(tz)
    today = now_local.date()
    if now_local.hour < settings.daily_digest_hour:
        return
    async for session in get_session():
        gaps = await users_with_gap(session, today=today, gap_business_days=3)
        for info in gaps:
            if _last_gap_nudge_by_user.get(info.user.id) == today:
                continue
            if info.last_day is None:
                text = t("gap_nudge_no_entries")
            else:
                text = t(
                    "gap_nudge_with_last",
                    last_day=info.last_day.isoformat(),
                    gap=info.gap_business_days,
                )
            try:
                await bot.send_message(info.user.tg_id, text)
                _last_gap_nudge_by_user[info.user.id] = today
            except TelegramAPIError:
                logger.warning("gap_nudge_send_failed", user_id=info.user.id)
        # Read-only flow but commit anyway to keep the session pattern consistent.
        await session.commit()


async def _maybe_send_debt_pings(bot: Bot, settings: Settings) -> None:
    """On Monday after the digest hour, DM each user a summary of periods
    older than 30 days that are still pending/partial. At most once per
    ISO week per user.
    """
    tz = ZoneInfo(settings.timezone)
    now_local = _now_local(tz)
    if now_local.weekday() != 0:  # Monday only
        return
    if now_local.hour < settings.daily_digest_hour:
        return
    today = now_local.date()
    iso_year, iso_week, _ = today.isocalendar()
    iso_key = (iso_year, iso_week)
    async for session in get_session():
        users = (await session.execute(select(User))).scalars().all()
        for u in users:
            if _last_debt_ping_iso_week_by_user.get(u.id) == iso_key:
                continue
            aged = await aged_open_periods(
                session, user=u, tz=tz, today=today, min_age_days=30,
            )
            if not aged:
                _last_debt_ping_iso_week_by_user[u.id] = iso_key
                continue
            lines = [t("debt_ping_header")]
            total = Decimal(0)
            for led in aged:
                remaining = led.remaining
                if remaining is None:
                    continue
                total += remaining
                period = f"{_RU_MONTHS_SCH[led.month - 1]} {led.year}"
                lines.append(
                    t(
                        "debt_ping_row",
                        period=period,
                        remaining=f"{remaining:.2f}",
                        currency=u.currency,
                    ),
                )
            lines.append("")
            lines.append(
                t(
                    "debt_ping_footer",
                    total=f"{total.quantize(Decimal('0.01')):.2f}",
                    currency=u.currency,
                ),
            )
            try:
                await bot.send_message(u.tg_id, "\n".join(lines))
                _last_debt_ping_iso_week_by_user[u.id] = iso_key
            except TelegramAPIError:
                logger.warning("debt_ping_send_failed", user_id=u.id)
        await session.commit()


async def _maybe_reassert_webhook(bot: Bot, settings: Settings) -> None:
    """Self-heal: if the webhook registration drifted away from our URL
    (e.g., wiped by an overlapping deploy's shutdown), re-register it.

    Cheap: one getWebhookInfo per tick + a setWebhook only when the URL
    differs.
    """
    if not (settings.webhook_url and settings.webhook_secret):
        return
    expected = settings.webhook_url.strip().rstrip("/") + settings.webhook_path
    try:
        info = await bot.get_webhook_info()
    except TelegramAPIError:
        logger.warning("webhook_self_heal_info_failed")
        return
    if info.url == expected:
        return
    logger.warning(
        "webhook_self_heal_reasserting",
        current=info.url,
        expected=expected,
    )
    try:
        await bot.set_webhook(
            url=expected,
            secret_token=settings.webhook_secret,
            drop_pending_updates=False,
        )
        logger.info("webhook_self_heal_done")
    except TelegramAPIError:
        logger.exception("webhook_self_heal_set_failed")


async def run_webhook_healer(bot: Bot, settings: Settings) -> None:
    """Tight loop (30s) that re-registers the webhook if Telegram lost it.

    Separate from the 5-minute maintenance scheduler so we can recover
    from a deploy-handover race in well under a minute.
    """
    while True:
        try:
            await _maybe_reassert_webhook(bot, settings)
        except Exception:  # noqa: BLE001
            logger.exception("webhook_healer_failed")
        await asyncio.sleep(30)


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
            await _maybe_send_day_reminders(bot, settings)
            await _maybe_send_gap_nudges(bot, settings)
            await _maybe_send_debt_pings(bot, settings)
        except Exception:  # noqa: BLE001
            logger.exception("scheduler_iteration_failed")
        await asyncio.sleep(interval)
