"""Phase 6.3: first-run onboarding wizard — service layer.

A worker is "onboarded" once they finish the wizard (`/start` for new
chats). The wizard captures their display name, optional hourly rate,
and optional evening-reminder hour, then sets `users.onboarded_at`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import User

# Re-use the money parser from advances so input validation is consistent
# with the rest of the bot.
from src.services.advances import parse_amount as _parse_amount


def is_onboarded(user: User) -> bool:
    return user.onboarded_at is not None


def parse_rate(raw: str) -> Decimal | None:
    """Reuse the money parser; returns a Decimal in [0.01, 1_000_000]."""
    return _parse_amount(raw)


async def complete_onboarding(
    session: AsyncSession,
    *,
    user_id: int,
    name: str,
    hourly_rate: Decimal | None,
    remind_hour_local: int | None,
) -> User:
    """Persist the wizard outcome on the user row.

    Raises ``ValueError`` if the user no longer exists. We rely on the
    caller to commit the session.
    """
    user = await session.get(User, user_id)
    if user is None:
        raise ValueError(f"user not found: {user_id}")
    cleaned = name.strip()
    if cleaned:
        user.name = cleaned[:80]
    if hourly_rate is not None:
        user.hourly_rate = hourly_rate
    if remind_hour_local is not None:
        if not (0 <= remind_hour_local <= 23):
            raise ValueError(f"bad hour: {remind_hour_local}")
        user.remind_hour_local = remind_hour_local
        user.day_reminder_last_sent = None
    user.onboarded_at = datetime.now(tz=UTC)
    return user
