"""Phase 5.3: evening day-entry reminder service.

A user gets a single reminder per local day, after their configured
``remind_hour_local`` (NULL = disabled). The reminder is skipped if the
user has already recorded a day-entry for today.

Phase 7.9: callers may pass ``resolve_tz`` to score eligibility against
each user's own timezone instead of the bot-wide default. The single-tz
path is preserved for callers that don't care (and so existing tests
stay valid).
"""

from __future__ import annotations

from collections.abc import Callable
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
    resolve_tz: Callable[[User], ZoneInfo] | None = None,
) -> list[User]:
    """Return users whose configured local reminder hour has passed today
    and who haven't yet recorded a day-entry for today (and haven't already
    received today's reminder).

    When ``resolve_tz`` is provided, each user's hour and "today" date are
    computed against the timezone returned by ``resolve_tz(user)``. The
    default-tz ``tz`` is still used as the reference clock for ``now``.
    """
    now_local = now.astimezone(tz) if now is not None else datetime.now(tz=tz)

    if resolve_tz is None:
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
        candidates = [
            u for u in candidates if u.day_reminder_last_sent != today
        ]
        if not candidates:
            return []
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

    # Per-user tz path: SQL filter on hour is unsafe because every user's
    # "local hour" differs, so we filter in Python.
    candidates = list(
        (
            await session.execute(
                select(User).where(User.remind_hour_local.is_not(None)),
            )
        ).scalars().all(),
    )
    eligible: list[tuple[User, date]] = []
    for u in candidates:
        u_tz = resolve_tz(u)
        local = now_local.astimezone(u_tz)
        if u.remind_hour_local is None or local.hour < u.remind_hour_local:
            continue
        if u.day_reminder_last_sent == local.date():
            continue
        eligible.append((u, local.date()))
    if not eligible:
        return []
    user_ids = [u.id for u, _ in eligible]
    dates = list({d for _, d in eligible})
    rows = (
        await session.execute(
            select(DayEntry.user_id, DayEntry.day).where(
                DayEntry.user_id.in_(user_ids),
                DayEntry.day.in_(dates),
            ),
        )
    ).all()
    have_entry = {(row[0], row[1]) for row in rows}
    return [u for u, d in eligible if (u.id, d) not in have_entry]


async def mark_reminded(
    session: AsyncSession, *, user: User, today: date,
) -> None:
    user.day_reminder_last_sent = today
    await session.flush()
