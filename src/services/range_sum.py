"""Phase 7.x: ``/range`` — sum hours × rate over an arbitrary date range.

Useful when a worker needs the gross earnings for a custom window (e.g.
a project sub-month, or two pay-periods stitched together). DayEntry
``hours`` are summed; the ``DAY_OFF`` marker rows are excluded, so the
projection lines up with the existing day-entries reports.

Earnings are ``hours * user.hourly_rate``. When the user has no rate
configured we still report the hours and return ``earnings=None`` so the
caller can render a hours-only message.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DayEntry, User
from src.services.day_entries import is_day_off


@dataclass
class RangeSum:
    start: date
    end: date
    days_with_hours: int
    total_hours: Decimal
    total_earnings: Decimal | None


def parse_iso_date(raw: str) -> date | None:
    """Parse ``YYYY-MM-DD`` -> ``date``. ``None`` on bad input."""
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


async def compute_range_sum(
    session: AsyncSession, *, user: User, start: date, end: date,
) -> RangeSum:
    """Sum DayEntry hours in [start, end]. Day-off rows are excluded."""
    rows = (
        await session.execute(
            select(DayEntry).where(
                DayEntry.user_id == user.id,
                DayEntry.day >= start,
                DayEntry.day <= end,
            ),
        )
    ).scalars().all()
    total_hours = Decimal(0)
    days_with_hours = 0
    for entry in rows:
        if is_day_off(entry.hours):
            continue
        total_hours += entry.hours
        days_with_hours += 1
    total_hours = total_hours.quantize(Decimal("0.01"))
    if user.hourly_rate is None:
        earnings: Decimal | None = None
    else:
        earnings = (total_hours * user.hourly_rate).quantize(Decimal("0.01"))
    return RangeSum(
        start=start,
        end=end,
        days_with_hours=days_with_hours,
        total_hours=total_hours,
        total_earnings=earnings,
    )
