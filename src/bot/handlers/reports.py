"""Report handlers: /today, /week, /month."""

from datetime import date, timedelta
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Break
from src.services.breaks import get_breaks_for_shifts
from src.services.reports import compute_period_hours, get_shifts_for_period
from src.services.shifts import ensure_user

router = Router()


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    assert message.from_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    today = date.today()

    breaks_by_shift: dict[int, list[Break]] = {}
    async for session in get_session():
        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        shifts = await get_shifts_for_period(session, user.id, today, today, tz)
        breaks_by_shift = await get_breaks_for_shifts(session, [s.id for s in shifts])

    if not shifts:
        await message.answer(t("no_shifts_today"))
        return

    closed = [s for s in shifts if s.end_at is not None]
    hours = compute_period_hours(closed, today, today, tz, breaks_by_shift)
    await message.answer(t("today_summary", hours=str(hours), count=str(len(closed))))


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    assert message.from_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())

    breaks_by_shift: dict[int, list[Break]] = {}
    async for session in get_session():
        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        shifts = await get_shifts_for_period(session, user.id, start_of_week, today, tz)
        breaks_by_shift = await get_breaks_for_shifts(session, [s.id for s in shifts])

    if not shifts:
        await message.answer(t("no_shifts_week"))
        return

    closed = [s for s in shifts if s.end_at is not None]
    hours = compute_period_hours(closed, start_of_week, today, tz, breaks_by_shift)
    await message.answer(t("week_summary", hours=str(hours), count=str(len(closed))))


@router.message(Command("month"))
async def cmd_month(message: Message) -> None:
    assert message.from_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    today = date.today()
    start_of_month = today.replace(day=1)

    breaks_by_shift: dict[int, list[Break]] = {}
    async for session in get_session():
        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        shifts = await get_shifts_for_period(session, user.id, start_of_month, today, tz)
        breaks_by_shift = await get_breaks_for_shifts(session, [s.id for s in shifts])

    if not shifts:
        await message.answer(t("no_shifts_month"))
        return

    closed = [s for s in shifts if s.end_at is not None]
    hours = compute_period_hours(closed, start_of_month, today, tz, breaks_by_shift)
    await message.answer(t("month_summary", hours=str(hours), count=str(len(closed))))
