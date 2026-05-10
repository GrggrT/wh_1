"""Report handlers: /today, /me_yesterday, /week, /month, /me <YYYY-MM>."""

import re
from datetime import date, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Break, Shift, Site, User
from src.services.breaks import get_breaks_for_shifts
from src.services.reports import (
    compute_period_earnings,
    compute_period_hours,
    get_shifts_for_period,
)
from src.services.shifts import ensure_user

router = Router()


async def _fetch_sites_map(
    session: AsyncSession, shifts: list[Shift],
) -> dict[int, Site]:
    site_ids = {s.site_id for s in shifts if s.site_id is not None}
    if not site_ids:
        return {}
    res = await session.execute(select(Site).where(Site.id.in_(site_ids)))
    return {s.id: s for s in res.scalars().all()}


def _format_summary(
    template_key: str,
    template_amount_key: str,
    hours: Decimal,
    count: int,
    amount: Decimal | None,
) -> str:
    if amount is None:
        return t(template_key, hours=str(hours), count=str(count))
    return t(
        template_amount_key,
        hours=str(hours),
        count=str(count),
        amount=str(amount),
    )


async def _period_summary(
    message: Message,
    start_date: date,
    end_date: date,
    empty_key: str,
    summary_key: str,
    summary_amount_key: str,
) -> None:
    assert message.from_user is not None
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    breaks_by_shift: dict[int, list[Break]] = {}
    sites_map: dict[int, Site] = {}
    user_rate: Decimal | None = None
    shifts: list[Shift] = []
    async for session in get_session():
        user: User = await ensure_user(
            session, message.from_user.id, message.from_user.full_name,
        )
        user_rate = user.hourly_rate
        shifts = await get_shifts_for_period(
            session, user.id, start_date, end_date, tz,
        )
        breaks_by_shift = await get_breaks_for_shifts(
            session, [s.id for s in shifts],
        )
        sites_map = await _fetch_sites_map(session, shifts)

    if not shifts:
        await message.answer(t(empty_key))
        return

    closed = [s for s in shifts if s.end_at is not None]
    hours = compute_period_hours(closed, start_date, end_date, tz, breaks_by_shift)
    amount = compute_period_earnings(
        closed, start_date, end_date, tz, sites_map, user_rate, breaks_by_shift,
    )
    await message.answer(
        _format_summary(summary_key, summary_amount_key, hours, len(closed), amount),
    )


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    today = date.today()
    await _period_summary(
        message, today, today,
        "no_shifts_today", "today_summary", "today_summary_amount",
    )


@router.message(Command("me_yesterday"))
async def cmd_me_yesterday(message: Message) -> None:
    yesterday = date.today() - timedelta(days=1)
    await _period_summary(
        message, yesterday, yesterday,
        "no_shifts_yesterday", "yesterday_summary", "yesterday_summary_amount",
    )


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    await _period_summary(
        message, start_of_week, today,
        "no_shifts_week", "week_summary", "week_summary_amount",
    )


@router.message(Command("month"))
async def cmd_month(message: Message) -> None:
    today = date.today()
    start_of_month = today.replace(day=1)
    await _period_summary(
        message, start_of_month, today,
        "no_shifts_month", "month_summary", "month_summary_amount",
    )


_PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


@router.message(Command("me"))
async def cmd_me_month(message: Message, command: CommandObject) -> None:
    """Self-report for an arbitrary calendar month: /me YYYY-MM."""
    if not command.args:
        await message.answer(t("me_usage"))
        return
    match = _PERIOD_RE.match(command.args.strip())
    if match is None:
        await message.answer(t("me_usage"))
        return
    year, month = int(match.group(1)), int(match.group(2))
    if not (1 <= month <= 12):
        await message.answer(t("me_usage"))
        return
    start = date(year, month, 1)
    end = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    ) - timedelta(days=1)
    await _period_summary(
        message, start, end,
        "no_shifts_month", "month_summary", "month_summary_amount",
    )
