"""Phase 5.1: simplified daily hours entry — service layer.

A `DayEntry` is one row per (user, day) holding the net hours the worker
reports at the end of the day. This is the simple flow that replaces
clock-in/out as the default UX in Phase 5.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DayEntry

# Quick-pick values shown on the inline keyboard (the smart-suggested value,
# when present, is prepended and the list is de-duplicated).
QUICK_HOURS: tuple[Decimal, ...] = (
    Decimal("6"),
    Decimal("7"),
    Decimal("8"),
    Decimal("9"),
    Decimal("10"),
    Decimal("12"),
)

# How many recent days to inspect for the smart-suggest modal value.
SUGGEST_WINDOW_DAYS = 5
# Minimum count for a value to be considered "habitual" within the window.
SUGGEST_MIN_OCCURRENCES = 3

# Hard limits to keep input sane.
MIN_HOURS = Decimal("0.25")
MAX_HOURS = Decimal("24")


def parse_hours(raw: str) -> Decimal | None:
    """Parse a user-supplied hours string. Returns ``None`` on bad input."""
    text = raw.strip().replace(",", ".")
    if not text:
        return None
    try:
        value = Decimal(text)
    except (ValueError, ArithmeticError):
        return None
    if value < MIN_HOURS or value > MAX_HOURS:
        return None
    # Quantize to two decimal places.
    return value.quantize(Decimal("0.01"))


async def upsert_day_entry(
    session: AsyncSession,
    *,
    user_id: int,
    day: date,
    hours: Decimal,
    site_id: int | None = None,
    note: str | None = None,
) -> tuple[DayEntry, bool]:
    """Insert or update the day-entry for (user, day). Returns (entry, created)."""
    existing = (
        await session.execute(
            select(DayEntry).where(
                DayEntry.user_id == user_id, DayEntry.day == day,
            ),
        )
    ).scalar_one_or_none()
    if existing is None:
        entry = DayEntry(
            user_id=user_id,
            day=day,
            hours=hours,
            site_id=site_id,
            note=note,
        )
        session.add(entry)
        await session.flush()
        return entry, True
    existing.hours = hours
    if site_id is not None:
        existing.site_id = site_id
    if note is not None:
        existing.note = note
    await session.flush()
    return existing, False


async def get_day_entry(
    session: AsyncSession, *, user_id: int, day: date,
) -> DayEntry | None:
    """Fetch the entry for (user, day) or ``None``."""
    return (
        await session.execute(
            select(DayEntry).where(
                DayEntry.user_id == user_id, DayEntry.day == day,
            ),
        )
    ).scalar_one_or_none()


async def list_recent_entries(
    session: AsyncSession, *, user_id: int, days: int = 14,
) -> list[DayEntry]:
    """Return the user's entries within the last ``days`` days, newest first."""
    cutoff = date.today() - timedelta(days=days - 1)
    return list(
        (
            await session.execute(
                select(DayEntry)
                .where(DayEntry.user_id == user_id, DayEntry.day >= cutoff)
                .order_by(desc(DayEntry.day)),
            )
        ).scalars().all(),
    )


def smart_suggest(entries: list[DayEntry]) -> Decimal | None:
    """Return the modal hours value if it's "habitual" within the window.

    The window is the most recent ``SUGGEST_WINDOW_DAYS`` entries (regardless
    of whether days were skipped); we return a value only if it appears at
    least ``SUGGEST_MIN_OCCURRENCES`` times. Otherwise ``None``.
    """
    if not entries:
        return None
    window = entries[:SUGGEST_WINDOW_DAYS]
    counts = Counter(e.hours for e in window)
    most_common_value, occurrences = counts.most_common(1)[0]
    if occurrences < SUGGEST_MIN_OCCURRENCES:
        return None
    return Decimal(most_common_value)


def quick_pick_values(
    suggested: Decimal | None = None,
) -> list[Decimal]:
    """Build the quick-pick row. Suggested value (if any) is placed first."""
    base = list(QUICK_HOURS)
    if suggested is None:
        return base
    deduped = [v for v in base if v != suggested]
    return [suggested, *deduped]


def format_hours(value: Decimal) -> str:
    """Pretty-print hours: drop trailing zeros, "8" instead of "8.00"."""
    normalized = value.normalize()
    # Decimal("8").normalize() → 8E+0; force fixed-point.
    if normalized == normalized.to_integral_value():
        return str(normalized.quantize(Decimal("1")))
    return str(normalized)
