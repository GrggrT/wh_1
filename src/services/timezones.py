"""Phase 7.9: per-user timezone resolver.

``User.timezone`` is an opt-in IANA name; NULL means "fall back to the
bot-wide default". A misconfigured row (string that ``ZoneInfo`` can't
load) also falls back rather than raising, so scheduler tasks don't take
the whole loop down because of a single bad value.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.core.config import Settings
from src.core.models import User


def user_tz(user: User, settings: Settings) -> ZoneInfo:
    """Resolve the effective timezone for ``user``.

    Falls back to ``settings.timezone`` when the user has no override or
    when the stored IANA name fails to load.
    """
    raw = user.timezone
    if raw:
        try:
            return ZoneInfo(raw)
        except ZoneInfoNotFoundError:
            pass
    return ZoneInfo(settings.timezone)
