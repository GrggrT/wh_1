"""Phase 5.3: evening day-entry reminder service.

A user gets a single reminder per local day, after their configured
``remind_hour_local`` (NULL = disabled). The reminder is skipped if the
user has already recorded a day-entry for today.
"""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import DayEntry, User


async def find_users_needing_reminder(
    session: AsyncSession,
    *,
    tz: ZoneInfo,
    now: datetime | None = None,
) -> list[User]:
    """Return users whose configured local reminder hour has passed today
    and who haven't yet recorded a day-entry for today (and haven't already
    received today's reminder)."""
    now_local = now.astimezone(tz) if now is not None else datetime.now(tz=tz)
    today = now_local.date()
    current_hour = now_local.hour

    candidates = list(
        (
            await session.execute(
                select(User).where(
                    User.remind_hour_local.is_not(None),
                    User.remind_hour_local <= current_hour,
                ),
            )
        ).scalars().all(),
    )
    if not candidates:
        return []
    # Filter out users already reminded today.
    candidates = [
        u for u in candidates if u.day_reminder_last_sent != today
    ]
    if not candidates:
        return []
    # Filter out users who already have a day_entry for today.
    user_ids = [u.id for u in candidates]
    have_entry_rows = (
        await session.execute(
            select(DayEntry.user_id).where(
                DayEntry.user_id.in_(user_ids), DayEntry.day == today,
            ),
        )
    ).all()
    have_entry = {row[0] for row in have_entry_rows}
    return [u for u in candidates if u.id not in have_entry]


async def mark_reminded(
    session: AsyncSession, *, user: User, today: date,
) -> None:
    user.day_reminder_last_sent = today
    await session.flush()
