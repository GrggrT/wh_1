"""Phase 7.2: smart reminders.

Two pure-ish helpers used by ``scheduler_runner``:

- ``users_with_gap`` — list users who haven't entered any hours for the
  past ``gap_business_days`` weekdays (Mon-Fri). Weekend-only gaps are
  ignored. Returns (user, last_entry_day, gap_business_days). When the
  user has no entries at all, ``last_entry_day`` is ``None``.
- ``aged_open_periods`` — list of open ledgers older than
  ``min_age_days`` (default 30) for the given user. Useful for the
  weekly debt ping.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DayEntry, User
from src.services.accounting import PeriodLedger, list_open_periods


@dataclass(frozen=True)
class GapInfo:
    user: User
    last_day: date | None
    gap_business_days: int


def _business_days_between(start_exclusive: date, end_inclusive: date) -> int:
    """Count Mon-Fri days in ``(start, end]``. Negative ranges return 0."""
    if end_inclusive <= start_exclusive:
        return 0
    days = 0
    d = start_exclusive + timedelta(days=1)
    while d <= end_inclusive:
        if d.weekday() < 5:  # Mon=0..Fri=4
            days += 1
        d += timedelta(days=1)
    return days


def _business_days_up_to(today: date, days: int) -> int:
    """Count Mon-Fri days in the last ``days`` calendar days ending today."""
    start_excl = today - timedelta(days=days)
    return _business_days_between(start_excl, today)


async def users_with_gap(
    session: AsyncSession,
    *,
    today: date,
    gap_business_days: int = 3,
) -> list[GapInfo]:
    """Return users whose most recent ``DayEntry.day`` is at least
    ``gap_business_days`` weekdays in the past.

    Users without *any* day entries are included only if today's date is
    far enough from when their account was created that ``gap_business_days``
    weekdays have already passed; otherwise we'd nudge users on day 1.
    """
    # Latest day per user via SQL aggregate.
    stmt = select(
        DayEntry.user_id, func.max(DayEntry.day).label("last_day"),
    ).group_by(DayEntry.user_id)
    rows = (await session.execute(stmt)).all()
    last_day_by_user: dict[int, date] = {
        int(uid): last for uid, last in rows
    }

    users = (await session.execute(select(User))).scalars().all()

    out: list[GapInfo] = []
    for u in users:
        last = last_day_by_user.get(u.id)
        if last is None:
            # No entries ever. Only nudge if account is old enough that the
            # user has had time to log something.
            account_day = u.created_at.date() if u.created_at else today
            biz = _business_days_between(account_day, today)
            if biz >= gap_business_days:
                out.append(GapInfo(user=u, last_day=None, gap_business_days=biz))
            continue
        biz = _business_days_between(last, today)
        if biz >= gap_business_days:
            out.append(GapInfo(user=u, last_day=last, gap_business_days=biz))
    return out


async def aged_open_periods(
    session: AsyncSession,
    *,
    user: User,
    tz: ZoneInfo,
    today: date,
    min_age_days: int = 30,
    lookback_months: int = 12,
) -> list[PeriodLedger]:
    """Return open (pending/partial) ledgers whose period ended at least
    ``min_age_days`` calendar days ago.
    """
    open_ledgers = await list_open_periods(
        session, user=user, tz=tz, today=today, lookback_months=lookback_months,
    )
    aged: list[PeriodLedger] = []
    for led in open_ledgers:
        # End-of-period date: last day of the led.year / led.month.
        if led.month == 12:
            next_first = date(led.year + 1, 1, 1)
        else:
            next_first = date(led.year, led.month + 1, 1)
        period_end = next_first - timedelta(days=1)
        age_days = (today - period_end).days
        if age_days >= min_age_days:
            aged.append(led)
    return aged


__all__ = [
    "GapInfo",
    "aged_open_periods",
    "users_with_gap",
]
