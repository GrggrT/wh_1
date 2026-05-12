"""Phase 5.2: advances + monthly salary computation.

A salary for month M:
    earnings_from_day_entries(user, M)
  + earnings_from_legacy_shifts(user, M)
  − advances_total(user, M)
  = net payable

Rate resolution:
- For a day-entry with a site rate → use site.hourly_rate
- Otherwise fall back to user.hourly_rate
- If neither is set, hours are still counted but not priced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Advance, DayEntry, Shift, Site, User
from src.services.breaks import get_breaks_for_shifts
from src.services.reports import compute_period_earnings

_AMOUNT_RE = re.compile(r"^\d+(?:\.\d+)?$")


def parse_amount(raw: str) -> Decimal | None:
    """Parse a money amount from user input (PLN). Positive only."""
    text = raw.strip().replace(",", ".")
    if not _AMOUNT_RE.match(text):
        return None
    value = Decimal(text)
    if value <= 0 or value > Decimal("1000000"):
        return None
    return value.quantize(Decimal("0.01"))


def parse_year_month(raw: str) -> tuple[int, int] | None:
    """Parse 'YYYY-MM' → (year, month). Returns None on bad input."""
    parts = raw.strip().split("-")
    if len(parts) != 2:
        return None
    try:
        year = int(parts[0])
        month = int(parts[1])
    except ValueError:
        return None
    if not (2000 <= year <= 2100):
        return None
    if not (1 <= month <= 12):
        return None
    return year, month


def month_bounds(year: int, month: int) -> tuple[date, date]:
    """Return (first_day, last_day) inclusive for the given calendar month."""
    first = date(year, month, 1)
    next_first = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    last = next_first - timedelta(days=1)
    return first, last


async def record_advance(
    session: AsyncSession,
    *,
    user_id: int,
    amount: Decimal,
    recorded_by_id: int,
    day: date,
    period_year: int | None = None,
    period_month: int | None = None,
    note: str | None = None,
) -> Advance:
    """Record a cash advance.

    ``day`` is the physical cash date. ``period_year``/``period_month`` is the
    accounting period the cash counts against (Phase 6.10b). When the period
    is omitted it defaults to the cash date's month, matching pre-6.10b
    semantics for callers that don't yet pass an explicit period.
    """
    py = period_year if period_year is not None else day.year
    pm = period_month if period_month is not None else day.month
    advance = Advance(
        user_id=user_id,
        amount=amount,
        day=day,
        period_year=py,
        period_month=pm,
        recorded_by_id=recorded_by_id,
        note=note,
    )
    session.add(advance)
    await session.flush()
    return advance


async def list_advances(
    session: AsyncSession,
    *,
    user_id: int,
    start: date,
    end: date,
) -> list[Advance]:
    """Advances for one user, inclusive date range, newest first."""
    return list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id == user_id,
                    Advance.day >= start,
                    Advance.day <= end,
                )
                .order_by(desc(Advance.day), desc(Advance.id)),
            )
        ).scalars().all(),
    )


async def list_advances_for_users(
    session: AsyncSession,
    *,
    user_ids: list[int],
    start: date,
    end: date,
) -> dict[int, list[Advance]]:
    """Advances grouped by user_id, filtered by cash-date range."""
    if not user_ids:
        return {}
    rows = list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id.in_(user_ids),
                    Advance.day >= start,
                    Advance.day <= end,
                )
                .order_by(desc(Advance.day)),
            )
        ).scalars().all(),
    )
    grouped: dict[int, list[Advance]] = {uid: [] for uid in user_ids}
    for a in rows:
        grouped.setdefault(a.user_id, []).append(a)
    return grouped


async def list_advances_for_period(
    session: AsyncSession,
    *,
    user_id: int,
    year: int,
    month: int,
) -> list[Advance]:
    """Advances declared for the (year, month) accounting period."""
    return list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id == user_id,
                    Advance.period_year == year,
                    Advance.period_month == month,
                )
                .order_by(desc(Advance.day), desc(Advance.id)),
            )
        ).scalars().all(),
    )


async def list_advances_for_users_period(
    session: AsyncSession,
    *,
    user_ids: list[int],
    year: int,
    month: int,
) -> dict[int, list[Advance]]:
    """Advances grouped by user_id, filtered by accounting period."""
    if not user_ids:
        return {}
    rows = list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id.in_(user_ids),
                    Advance.period_year == year,
                    Advance.period_month == month,
                )
                .order_by(desc(Advance.day)),
            )
        ).scalars().all(),
    )
    grouped: dict[int, list[Advance]] = {uid: [] for uid in user_ids}
    for a in rows:
        grouped.setdefault(a.user_id, []).append(a)
    return grouped


def _resolve_entry_rate(
    entry: DayEntry, sites_by_id: dict[int, Site], user_rate: Decimal | None,
) -> Decimal | None:
    if entry.site_id is not None:
        site = sites_by_id.get(entry.site_id)
        if site is not None and site.hourly_rate is not None:
            return site.hourly_rate
    return user_rate


def compute_day_entry_earnings(
    entries: list[DayEntry],
    sites_by_id: dict[int, Site],
    user_rate: Decimal | None,
) -> tuple[Decimal, Decimal | None]:
    """Sum hours and earnings across day entries.

    Returns (total_hours, total_earnings_or_None). Earnings is None only if
    nothing could be priced (i.e. no user_rate and no site rate anywhere).
    """
    total_hours = Decimal(0)
    total_earnings = Decimal(0)
    any_priced = False
    for e in entries:
        total_hours += e.hours
        rate = _resolve_entry_rate(e, sites_by_id, user_rate)
        if rate is None:
            continue
        any_priced = True
        total_earnings += e.hours * rate
    return (
        total_hours.quantize(Decimal("0.01")),
        total_earnings.quantize(Decimal("0.01")) if any_priced else None,
    )


@dataclass
class SalaryBreakdown:
    user_id: int
    year: int
    month: int
    day_entries_hours: Decimal
    day_entries_earnings: Decimal | None
    shifts_hours: Decimal
    shifts_earnings: Decimal | None
    advances_total: Decimal
    net_payable: Decimal | None  # None when nothing could be priced

    @property
    def total_hours(self) -> Decimal:
        return (self.day_entries_hours + self.shifts_hours).quantize(
            Decimal("0.01"),
        )

    @property
    def total_earnings(self) -> Decimal | None:
        if self.day_entries_earnings is None and self.shifts_earnings is None:
            return None
        return (
            (self.day_entries_earnings or Decimal(0))
            + (self.shifts_earnings or Decimal(0))
        ).quantize(Decimal("0.01"))


async def compute_salary(
    session: AsyncSession,
    *,
    user: User,
    year: int,
    month: int,
    tz: ZoneInfo,
) -> SalaryBreakdown:
    """Compute monthly salary for one user (day-entries + legacy shifts − advances)."""
    first_day, last_day = month_bounds(year, month)

    # --- day-entry side ----------------------------------------------------
    entries = list(
        (
            await session.execute(
                select(DayEntry).where(
                    DayEntry.user_id == user.id,
                    DayEntry.day >= first_day,
                    DayEntry.day <= last_day,
                ),
            )
        ).scalars().all(),
    )
    site_ids = {e.site_id for e in entries if e.site_id is not None}

    # --- legacy shifts side ------------------------------------------------
    period_start = datetime.combine(first_day, time.min, tzinfo=tz)
    period_end = datetime.combine(last_day + timedelta(days=1), time.min, tzinfo=tz)
    shifts = list(
        (
            await session.execute(
                select(Shift).where(
                    Shift.user_id == user.id,
                    Shift.start_at < period_end,
                    Shift.end_at.is_not(None),
                    Shift.end_at > period_start,
                ),
            )
        ).scalars().all(),
    )
    site_ids.update({s.site_id for s in shifts if s.site_id is not None})

    sites_by_id: dict[int, Site] = {}
    if site_ids:
        sres = await session.execute(
            select(Site).where(Site.id.in_(site_ids)),
        )
        sites_by_id = {s.id: s for s in sres.scalars().all()}

    de_hours, de_earnings = compute_day_entry_earnings(
        entries, sites_by_id, user.hourly_rate,
    )

    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in shifts],
    )
    shift_earnings = compute_period_earnings(
        shifts, first_day, last_day, tz, sites_by_id,
        user.hourly_rate, breaks_by_shift,
    )
    # Hours for the shift side, mirroring compute_period_earnings windowing.
    shift_hours = Decimal(0)
    for s in shifts:
        if s.end_at is None:
            continue
        eff_start = max(s.start_at, period_start)
        eff_end = min(s.end_at, period_end)
        if eff_end <= eff_start:
            continue
        from src.services.reports import compute_hours
        shift_hours += compute_hours(eff_start, eff_end)
    shift_hours = shift_hours.quantize(Decimal("0.01"))

    advances = await list_advances_for_period(
        session, user_id=user.id, year=year, month=month,
    )
    advances_total = sum(
        (a.amount for a in advances), Decimal(0),
    ).quantize(Decimal("0.01"))

    earnings_total: Decimal | None
    if de_earnings is None and shift_earnings is None:
        earnings_total = None
        net_payable: Decimal | None = None
    else:
        earnings_total = (
            (de_earnings or Decimal(0)) + (shift_earnings or Decimal(0))
        ).quantize(Decimal("0.01"))
        net_payable = (earnings_total - advances_total).quantize(Decimal("0.01"))

    return SalaryBreakdown(
        user_id=user.id,
        year=year,
        month=month,
        day_entries_hours=de_hours,
        day_entries_earnings=de_earnings,
        shifts_hours=shift_hours,
        shifts_earnings=shift_earnings,
        advances_total=advances_total,
        net_payable=net_payable,
    )
