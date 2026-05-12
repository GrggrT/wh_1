"""Report aggregation logic."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Break, Shift, Site
from src.services.breaks import total_break_hours


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
    shifts: list[Shift],
    start_date: date,
    end_date: date,
    tz: ZoneInfo,
    breaks_by_shift: dict[int, list[Break]] | None = None,
) -> Decimal:
    """Total NET hours within a date range; subtracts breaks clipped to window."""
    period_start = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    total = Decimal(0)

    for shift in shifts:
        if shift.end_at is None:
            continue
        effective_start = max(shift.start_at, period_start)
        effective_end = min(shift.end_at, period_end)
        if effective_end <= effective_start:
            continue
        gross = compute_hours(effective_start, effective_end)
        break_h = Decimal(0)
        if breaks_by_shift is not None:
            shift_breaks = breaks_by_shift.get(shift.id, [])
            if shift_breaks:
                break_h = total_break_hours(
                    shift_breaks, effective_start, effective_end,
                )
        net = gross - break_h
        if net < 0:
            net = Decimal(0)
        total += net

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


def compute_period_earnings(
    shifts: list[Shift],
    start_date: date,
    end_date: date,
    tz: ZoneInfo,
    sites_by_id: dict[int, Site],
    user_rate: Decimal | None,
    breaks_by_shift: dict[int, list[Break]] | None = None,
) -> Decimal | None:
    """Total earnings across closed shifts in the period.

    Per shift, rate = (site.hourly_rate if site has a rate) else user_rate.
    Returns None if no shift can be priced (no rate at all anywhere); otherwise
    sums priced shifts only. Hours used per shift are net (clipped to window).
    """
    period_start = datetime.combine(start_date, time.min, tzinfo=tz)
    period_end = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=tz)
    total = Decimal(0)
    any_priced = False
    for shift in shifts:
        if shift.end_at is None:
            continue
        effective_start = max(shift.start_at, period_start)
        effective_end = min(shift.end_at, period_end)
        if effective_end <= effective_start:
            continue
        gross = compute_hours(effective_start, effective_end)
        break_h = Decimal(0)
        if breaks_by_shift is not None:
            shift_breaks = breaks_by_shift.get(shift.id, [])
            if shift_breaks:
                break_h = total_break_hours(
                    shift_breaks, effective_start, effective_end,
                )
        net = gross - break_h
        if net < 0:
            net = Decimal(0)
        rate: Decimal | None = None
        if shift.site_id is not None:
            site = sites_by_id.get(shift.site_id)
            if site is not None and site.hourly_rate is not None:
                rate = site.hourly_rate
        if rate is None:
            rate = user_rate
        if rate is None:
            continue
        any_priced = True
        total += net * rate
    if not any_priced:
        return None
    return total.quantize(Decimal("0.01"))


async def get_site_for_shift(session: AsyncSession, site_id: int | None) -> Site | None:
    if site_id is None:
        return None
    stmt = select(Site).where(Site.id == site_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
