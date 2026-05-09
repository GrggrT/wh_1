"""Report aggregation logic."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Shift, Site


def compute_hours(start: datetime, end: datetime) -> Decimal:
    """Compute shift duration in hours using timedelta (not float math)."""
    delta: timedelta = end - start
    total_seconds = int(delta.total_seconds())
    return Decimal(total_seconds) / Decimal(3600)


def split_shift_at_midnight(
    start: datetime, end: datetime, tz: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    """Split a shift into segments at local midnight boundaries."""
    segments: list[tuple[datetime, datetime]] = []
    current_start = start.astimezone(tz)
    local_end = end.astimezone(tz)

    while current_start.date() < local_end.date():
        next_midnight = datetime.combine(
            current_start.date() + timedelta(days=1), time.min, tzinfo=tz
        )
        segments.append((current_start, next_midnight))
        current_start = next_midnight

    segments.append((current_start, local_end))
    return segments


async def get_shifts_for_period(
    session: AsyncSession, user_id: int, start_date: date, end_date: date, tz: ZoneInfo
) -> list[Shift]:
    """Get shifts that overlap with the given date range (in local tz)."""
    period_start = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)

    stmt = (
        select(Shift)
        .where(
            Shift.user_id == user_id,
            Shift.start_at < period_end,
            (Shift.end_at > period_start) | (Shift.end_at.is_(None)),
        )
        .order_by(Shift.start_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


def compute_period_hours(
    shifts: list[Shift], start_date: date, end_date: date, tz: ZoneInfo
) -> Decimal:
    """Total hours within a date range, accounting for midnight splits."""
    period_start = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    total = Decimal(0)

    for shift in shifts:
        if shift.end_at is None:
            continue
        effective_start = max(shift.start_at, period_start)
        effective_end = min(shift.end_at, period_end)
        if effective_end > effective_start:
            total += compute_hours(effective_start, effective_end)

    return total.quantize(Decimal("0.01"))


async def get_shifts_for_users_in_period(
    session: AsyncSession,
    user_ids: list[int],
    start_date: date,
    end_date: date,
    tz: ZoneInfo,
) -> list[Shift]:
    """Get shifts for a set of users overlapping the given local date range."""
    if not user_ids:
        return []
    period_start = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    stmt = (
        select(Shift)
        .where(
            Shift.user_id.in_(user_ids),
            Shift.start_at < period_end,
            (Shift.end_at > period_start) | (Shift.end_at.is_(None)),
        )
        .order_by(Shift.user_id, Shift.start_at)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_site_for_shift(session: AsyncSession, site_id: int | None) -> Site | None:
    if site_id is None:
        return None
    stmt = select(Site).where(Site.id == site_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
