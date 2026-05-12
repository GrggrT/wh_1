"""Phase 7.4: month-end forecast service.

Projects the current calendar month's total hours + earnings based on the
average per business day so far. Pure dataclass + small async builder; no
side effects.

Projection model
~~~~~~~~~~~~~~~~
- "business day" = Mon–Fri. We deliberately ignore weekends for the
  per-day average because a Saturday spike would distort projections.
- ``avg_per_business_day = mtd_hours / business_days_elapsed`` once at
  least one business day has elapsed, otherwise the forecast falls back
  to "no projection yet".
- Projected total = MTD + ``avg_per_business_day × business_days_remaining``.
- Earnings projection scales linearly off the hourly rate that
  ``compute_salary`` already used.
"""

from __future__ import annotations

import calendar as cal_mod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import User
from src.services.advances import compute_salary


def _business_days_in_month(year: int, month: int) -> int:
    last_day_num = cal_mod.monthrange(year, month)[1]
    return sum(
        1 for d in range(1, last_day_num + 1)
        if date(year, month, d).weekday() < 5
    )


def _business_days_elapsed(year: int, month: int, today: date) -> int:
    if today.year != year or today.month != month:
        # Either the period is fully past (return all business days)
        # or fully in the future (return 0).
        if (today.year, today.month) > (year, month):
            return _business_days_in_month(year, month)
        return 0
    return sum(
        1 for d in range(1, today.day + 1)
        if date(year, month, d).weekday() < 5
    )


@dataclass
class Forecast:
    year: int
    month: int
    mtd_hours: Decimal
    mtd_earnings: Decimal | None
    business_days_elapsed: int
    business_days_total: int
    projected_total_hours: Decimal | None
    projected_total_earnings: Decimal | None

    @property
    def business_days_remaining(self) -> int:
        return max(0, self.business_days_total - self.business_days_elapsed)

    @property
    def projected_additional_hours(self) -> Decimal | None:
        if self.projected_total_hours is None:
            return None
        return (self.projected_total_hours - self.mtd_hours).quantize(
            Decimal("0.01"),
        )


async def compute_forecast(
    session: AsyncSession,
    *,
    user: User,
    year: int,
    month: int,
    today: date,
    tz: ZoneInfo,
) -> Forecast:
    """Build a month-end projection for ``user`` in (year, month)."""
    breakdown = await compute_salary(
        session, user=user, year=year, month=month, tz=tz,
    )
    mtd_hours = breakdown.total_hours
    mtd_earnings = breakdown.total_earnings

    elapsed = _business_days_elapsed(year, month, today)
    total_bd = _business_days_in_month(year, month)
    remaining = max(0, total_bd - elapsed)

    if elapsed == 0 or remaining == 0:
        projected_hours = mtd_hours if remaining == 0 else None
        projected_earnings = mtd_earnings if remaining == 0 else None
    else:
        avg_hours = mtd_hours / Decimal(elapsed)
        extra_hours = (avg_hours * Decimal(remaining)).quantize(
            Decimal("0.01"),
        )
        projected_hours = (mtd_hours + extra_hours).quantize(Decimal("0.01"))
        if mtd_earnings is None or mtd_hours == 0:
            projected_earnings = None
        else:
            rate = mtd_earnings / mtd_hours
            projected_earnings = (
                projected_hours * rate
            ).quantize(Decimal("0.01"))

    return Forecast(
        year=year,
        month=month,
        mtd_hours=mtd_hours,
        mtd_earnings=mtd_earnings,
        business_days_elapsed=elapsed,
        business_days_total=total_bd,
        projected_total_hours=projected_hours,
        projected_total_earnings=projected_earnings,
    )


def end_of_month(year: int, month: int) -> date:
    last = cal_mod.monthrange(year, month)[1]
    return date(year, month, last)


__all__ = ["Forecast", "compute_forecast", "end_of_month"]
