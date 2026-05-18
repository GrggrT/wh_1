"""Daily and monthly digest builders for the bot owner."""

from collections.abc import Callable, Hashable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DayEntry, Shift, Site, User
from src.services.breaks import get_breaks_for_shifts, total_break_hours
from src.services.reports import compute_hours, compute_period_hours


def _fmt_hours(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _avg_per_day(total: Decimal, days: int) -> str:
    if days <= 0:
        return "0.00"
    return _fmt_hours(total / Decimal(days))


async def _day_entries_in_range(
    session: AsyncSession,
    start: date,
    end_inclusive: date,
) -> list[DayEntry]:
    """Return all DayEntry rows whose `day` falls in [start, end_inclusive]."""
    rows = (await session.execute(
        select(DayEntry).where(
            DayEntry.day >= start,
            DayEntry.day <= end_inclusive,
        ),
    )).scalars().all()
    return list(rows)


def _sum_hours(entries: list[DayEntry]) -> Decimal:
    total = Decimal(0)
    for e in entries:
        total += e.hours
    return total


def _distinct_days(entries: list[DayEntry]) -> int:
    return len({e.day for e in entries})


async def build_daily_digest(
    session: AsyncSession,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> str:
    """Daily summary based on DayEntry rows for today (in tz)."""
    current = (now or datetime.now(tz=tz)).astimezone(tz)
    today_local = current.date()

    entries = await _day_entries_in_range(session, today_local, today_local)
    if not entries:
        return f"Сводка за {today_local.isoformat()}: часы не записаны."

    total = _sum_hours(entries)
    return (
        f"Сводка за {today_local.isoformat()}:\n"
        f"• Часы: {_fmt_hours(total)}"
    )


async def build_monthly_digest(
    session: AsyncSession,
    tz: ZoneInfo,
    year: int,
    month: int,
) -> str:
    """Monthly summary based on DayEntry rows for the given calendar month."""
    next_month = (
        date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    )
    end_inclusive = next_month - timedelta(days=1)
    period_label = f"{year:04d}-{month:02d}"
    entries = await _day_entries_in_range(session, date(year, month, 1), end_inclusive)
    if not entries:
        return f"Месячная сводка за {period_label}: часы не записаны."

    total = _sum_hours(entries)
    days = _distinct_days(entries)
    lines = [
        f"Месячная сводка за {period_label}:",
        f"• Часы: {_fmt_hours(total)}",
        f"• Дней работы: {days}",
    ]
    if days:
        lines.append(f"• Среднее в день: {_avg_per_day(total, days)} ч")
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
    """Weekly summary based on DayEntry rows for [week_start, week_end]."""
    label = f"{week_start.isoformat()} … {week_end.isoformat()}"
    entries = await _day_entries_in_range(session, week_start, week_end)
    if not entries:
        return f"Недельная сводка ({label}): часы не записаны."

    total = _sum_hours(entries)
    days = _distinct_days(entries)
    lines = [
        f"Недельная сводка ({label}):",
        f"• Часы: {_fmt_hours(total)}",
        f"• Дней работы: {days}",
    ]
    if days:
        lines.append(f"• Среднее в день: {_avg_per_day(total, days)} ч")
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
