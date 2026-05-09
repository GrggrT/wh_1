"""Background maintenance: auto clock-out and shift reminders."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Shift, User

_UTC = ZoneInfo("UTC")


async def find_long_open_shifts(
    session: AsyncSession,
    max_hours: int,
    now: datetime | None = None,
) -> list[Shift]:
    """Return shifts open longer than max_hours."""
    current = now or datetime.now(tz=_UTC)
    cutoff = current - timedelta(hours=max_hours)
    stmt = select(Shift).where(Shift.end_at.is_(None), Shift.start_at <= cutoff)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def find_shifts_needing_reminder(
    session: AsyncSession,
    threshold_hours: int,
    max_hours: int,
    now: datetime | None = None,
) -> list[Shift]:
    """Return open shifts that crossed the reminder threshold but are not yet
    eligible for auto-close, and have not had a reminder sent yet."""
    current = now or datetime.now(tz=_UTC)
    threshold = current - timedelta(hours=threshold_hours)
    auto_close_cutoff = current - timedelta(hours=max_hours)
    stmt = select(Shift).where(
        Shift.end_at.is_(None),
        Shift.start_at <= threshold,
        Shift.start_at > auto_close_cutoff,
        Shift.reminder_sent_at.is_(None),
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def auto_close_shift(
    session: AsyncSession,
    shift: Shift,
    now: datetime | None = None,
) -> Shift:
    """Force-close a shift, marking it auto_closed."""
    shift.end_at = now or datetime.now(tz=_UTC)
    shift.auto_closed = True
    await session.flush()
    return shift


async def mark_reminder_sent(
    session: AsyncSession,
    shift: Shift,
    now: datetime | None = None,
) -> Shift:
    shift.reminder_sent_at = now or datetime.now(tz=_UTC)
    await session.flush()
    return shift


async def get_user_tg_id(session: AsyncSession, user_id: int) -> int | None:
    stmt = select(User.tg_id).where(User.id == user_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
