"""Daily and monthly digest builders for the bot owner."""

from collections.abc import Callable, Hashable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Shift, Site, User
from src.services.breaks import get_breaks_for_shifts, total_break_hours
from src.services.reports import compute_hours, compute_period_hours


def _days_worked(shifts: list[Shift], tz: ZoneInfo) -> int:
    """Distinct local-date count among closed shifts (by end_at)."""
    days: set[date] = set()
    for s in shifts:
        if s.end_at is None:
            continue
        days.add(s.end_at.astimezone(tz).date())
    return len(days)


def _fmt_hours(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _avg_per_day(total: Decimal, days: int) -> str:
    if days <= 0:
        return "0.00"
    return _fmt_hours(total / Decimal(days))


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

    if not any((started_count, closed_count, open_count)):
        return f"Сводка за {today_local.isoformat()}: смен не было."

    lines = [f"Сводка за {today_local.isoformat()}:"]
    if started_count:
        lines.append(f"• Открыто смен: {started_count}")
    if closed_count:
        auto_suffix = f" (в т.ч. авто: {auto_closed_today})" if auto_closed_today else ""
        lines.append(f"• Закрыто: {closed_count}{auto_suffix}")
    if open_count:
        lines.append(f"• Сейчас на смене: {open_count}")
    lines.append(f"• Часы (нетто): {_fmt_hours(total_hours)}")
    return "\n".join(lines)


async def build_monthly_digest(
    session: AsyncSession,
    tz: ZoneInfo,
    year: int,
    month: int,
) -> str:
    """Return a Russian summary of the given calendar month (in tz)."""
    period_start = datetime.combine(date(year, month, 1), time.min, tzinfo=tz)
    next_month = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    period_end = datetime.combine(next_month, time.min, tzinfo=tz)
    end_inclusive = next_month - timedelta(days=1)

    closed_shifts = list((await session.execute(
        select(Shift).where(
            Shift.end_at.is_not(None),
            Shift.end_at >= period_start,
            Shift.end_at < period_end,
        ),
    )).scalars().all())

    period_label = f"{year:04d}-{month:02d}"
    if not closed_shifts:
        return f"Месячная сводка за {period_label}: смен не было."

    auto_count = sum(1 for s in closed_shifts if s.auto_closed)
    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in closed_shifts],
    )
    total_hours = compute_period_hours(
        closed_shifts, date(year, month, 1), end_inclusive, tz, breaks_by_shift,
    )
    days = _days_worked(closed_shifts, tz)

    lines = [f"Месячная сводка за {period_label}:"]
    auto_suffix = f" (в т.ч. авто: {auto_count})" if auto_count else ""
    lines.append(f"• Закрыто смен: {len(closed_shifts)}{auto_suffix}")
    lines.append(f"• Часы (нетто): {_fmt_hours(total_hours)}")
    lines.append(f"• Дней работы: {days}")
    if days:
        lines.append(f"• Среднее в день: {_avg_per_day(total_hours, days)} ч")
    return "\n".join(lines)


def previous_full_week(today: date) -> tuple[date, date]:
    """Return (Monday, Sunday) of the calendar week immediately before `today`'s."""
    this_monday = today - timedelta(days=today.weekday())
    last_sunday = this_monday - timedelta(days=1)
    last_monday = this_monday - timedelta(days=7)
    return last_monday, last_sunday


async def build_weekly_digest(
    session: AsyncSession,
    tz: ZoneInfo,
    week_start: date,
    week_end: date,
) -> str:
    """Return a Russian summary of one calendar week (Mon..Sun) in tz."""
    period_start = datetime.combine(week_start, time.min, tzinfo=tz)
    period_end = datetime.combine(
        week_end + timedelta(days=1), time.min, tzinfo=tz,
    )

    closed_shifts = list((await session.execute(
        select(Shift).where(
            Shift.end_at.is_not(None),
            Shift.end_at >= period_start,
            Shift.end_at < period_end,
        ),
    )).scalars().all())

    label = f"{week_start.isoformat()} … {week_end.isoformat()}"
    if not closed_shifts:
        return f"Недельная сводка ({label}): смен не было."

    auto_count = sum(1 for s in closed_shifts if s.auto_closed)
    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in closed_shifts],
    )
    total_hours = compute_period_hours(
        closed_shifts, week_start, week_end, tz, breaks_by_shift,
    )
    days = _days_worked(closed_shifts, tz)

    lines = [f"Недельная сводка ({label}):"]
    auto_suffix = f" (в т.ч. авто: {auto_count})" if auto_count else ""
    lines.append(f"• Закрыто смен: {len(closed_shifts)}{auto_suffix}")
    lines.append(f"• Часы (нетто): {_fmt_hours(total_hours)}")
    lines.append(f"• Дней работы: {days}")
    if days:
        lines.append(f"• Среднее в день: {_avg_per_day(total_hours, days)} ч")
    return "\n".join(lines)


def previous_month(year: int, month: int) -> tuple[int, int]:
    """Calendar arithmetic helper: return (year, month) for the prior month."""
    if month == 1:
        return year - 1, 12
    return year, month - 1


async def build_global_stats(
    session: AsyncSession,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> str:
    """All-time + month-to-date summary across every user. Owner-only consumer."""
    current = (now or datetime.now(tz=tz)).astimezone(tz)
    today_local = current.date()
    month_start = datetime.combine(
        today_local.replace(day=1), time.min, tzinfo=tz,
    )

    total_shifts = (await session.execute(
        select(func.count(Shift.id)).where(Shift.end_at.is_not(None)),
    )).scalar_one()
    open_shifts = (await session.execute(
        select(func.count(Shift.id)).where(Shift.end_at.is_(None)),
    )).scalar_one()
    total_users = (await session.execute(
        select(func.count(User.id)),
    )).scalar_one()
    auto_total = (await session.execute(
        select(func.count(Shift.id)).where(Shift.auto_closed.is_(True)),
    )).scalar_one()

    all_closed = list((await session.execute(
        select(Shift).where(Shift.end_at.is_not(None)),
    )).scalars().all())
    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in all_closed],
    )
    if all_closed:
        first_dt = min(s.start_at for s in all_closed).astimezone(tz).date()
    else:
        first_dt = today_local
    total_hours = compute_period_hours(
        all_closed, first_dt, today_local, tz, breaks_by_shift,
    )

    mtd_closed = [s for s in all_closed if s.end_at is not None and s.end_at >= month_start]
    mtd_hours = compute_period_hours(
        mtd_closed,
        today_local.replace(day=1),
        today_local,
        tz,
        breaks_by_shift,
    )

    return (
        f"Глобальная статистика:\n"
        f"• Пользователей: {total_users}\n"
        f"• Всего смен (закрытых): {total_shifts} (в т.ч. авто: {auto_total})\n"
        f"• Сейчас открытых смен: {open_shifts}\n"
        f"• Часы за всё время (нетто): {total_hours}\n"
        f"• Часы с начала месяца: {mtd_hours}"
    )


async def _net_by_key[K: Hashable](
    session: AsyncSession,
    period_start: datetime,
    period_end: datetime,
    key_fn: Callable[[Shift], K],
) -> dict[K, tuple[Decimal, int]]:
    """Group net hours and shift count by a key derived from each closed shift.

    Returns mapping of key -> (net_hours, count). Hours are window-clipped
    against the period and breaks are subtracted clipped to the same window.
    """
    rows = list((await session.execute(
        select(Shift).where(
            Shift.end_at.is_not(None),
            Shift.end_at > period_start,
            Shift.start_at < period_end,
        ),
    )).scalars().all())
    breaks_by_shift = await get_breaks_for_shifts(
        session, [s.id for s in rows],
    )
    bucket: dict[K, tuple[Decimal, int]] = {}
    for s in rows:
        if s.end_at is None:
            continue
        eff_start = max(s.start_at, period_start)
        eff_end = min(s.end_at, period_end)
        if eff_end <= eff_start:
            continue
        gross = compute_hours(eff_start, eff_end)
        br = total_break_hours(
            breaks_by_shift.get(s.id, []), eff_start, eff_end,
        )
        net = gross - br
        if net < 0:
            net = Decimal(0)
        key = key_fn(s)
        prev_h, prev_c = bucket.get(key, (Decimal(0), 0))
        bucket[key] = (prev_h + net, prev_c + 1)
    return bucket


async def build_work_type_breakdown(
    session: AsyncSession,
    tz: ZoneInfo,
    year: int,
    month: int,
) -> str:
    """Per-work-type net hours/count for the given month."""
    first = date(year, month, 1)
    next_month_first = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    period_start = datetime.combine(first, time.min, tzinfo=tz)
    period_end = datetime.combine(next_month_first, time.min, tzinfo=tz)

    def _key(s: Shift) -> str:
        return (s.work_type or "").strip() or "—"

    buckets = await _net_by_key(session, period_start, period_end, _key)
    if not buckets:
        return f"Работы за {year:04d}-{month:02d}: данных нет."
    rows = sorted(
        buckets.items(),
        key=lambda kv: kv[1][0],
        reverse=True,
    )
    lines = [f"Часы по типам работ за {year:04d}-{month:02d}:"]
    for key, (h, c) in rows:
        lines.append(f"• {key}: {h.quantize(Decimal('0.01'))} ч ({c})")
    return "\n".join(lines)


async def build_site_breakdown(
    session: AsyncSession,
    tz: ZoneInfo,
    year: int,
    month: int,
) -> str:
    """Per-site net hours/count for the given month."""
    first = date(year, month, 1)
    next_month_first = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    period_start = datetime.combine(first, time.min, tzinfo=tz)
    period_end = datetime.combine(next_month_first, time.min, tzinfo=tz)

    def _key(s: Shift) -> int | None:
        return s.site_id

    buckets = await _net_by_key(session, period_start, period_end, _key)
    if not buckets:
        return f"Объекты за {year:04d}-{month:02d}: данных нет."

    site_ids = {k for k in buckets if isinstance(k, int)}
    sites_map: dict[int, str] = {}
    if site_ids:
        sres = await session.execute(
            select(Site).where(Site.id.in_(site_ids)),
        )
        sites_map = {s.id: s.name for s in sres.scalars().all()}

    rows = sorted(
        buckets.items(),
        key=lambda kv: kv[1][0],
        reverse=True,
    )
    lines = [f"Часы по объектам за {year:04d}-{month:02d}:"]
    for key, (h, c) in rows:
        name = sites_map.get(key, "—") if isinstance(key, int) else "—"
        lines.append(f"• {name}: {h.quantize(Decimal('0.01'))} ч ({c})")
    return "\n".join(lines)
