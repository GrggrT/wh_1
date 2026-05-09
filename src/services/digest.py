"""Daily digest builder for the bot owner."""

from datetime import datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Shift
from src.services.breaks import get_breaks_for_shifts
from src.services.reports import compute_period_hours


async def build_daily_digest(
    session: AsyncSession,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> str:
    """Return a short Russian summary of today's activity in tz."""
    current = (now or datetime.now(tz=tz)).astimezone(tz)
    today_local = current.date()
    period_start = datetime.combine(today_local, time.min, tzinfo=tz)
    period_end = period_start + timedelta(days=1)

    started_count = (await session.execute(
        select(func.count(Shift.id)).where(
            Shift.start_at >= period_start,
            Shift.start_at < period_end,
        ),
    )).scalar_one()

    closed_count = (await session.execute(
        select(func.count(Shift.id)).where(
            Shift.end_at >= period_start,
            Shift.end_at < period_end,
        ),
    )).scalar_one()

    open_count = (await session.execute(
        select(func.count(Shift.id)).where(Shift.end_at.is_(None)),
    )).scalar_one()

    auto_closed_today = (await session.execute(
        select(func.count(Shift.id)).where(
            Shift.auto_closed.is_(True),
            Shift.end_at >= period_start,
            Shift.end_at < period_end,
        ),
    )).scalar_one()

    overlapping_shifts = list((await session.execute(
        select(Shift).where(
            Shift.start_at < period_end,
            (Shift.end_at > period_start) | (Shift.end_at.is_(None)),
        ),
    )).scalars().all())

    closed_for_hours = [s for s in overlapping_shifts if s.end_at is not None]
    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in closed_for_hours],
    )
    total_hours = compute_period_hours(
        closed_for_hours, today_local, today_local, tz, breaks_by_shift,
    )

    return (
        f"Сводка за {today_local.isoformat()}:\n"
        f"• Открыто смен: {started_count}\n"
        f"• Закрыто: {closed_count} (в т.ч. авто: {auto_closed_today})\n"
        f"• Сейчас на смене: {open_count}\n"
        f"• Часы (нетто): {total_hours.quantize(Decimal('0.01'))}"
    )
