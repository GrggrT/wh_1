"""Phase 5.5: gate `/command` entry points behind product-mode toggles.

The middleware only intercepts `/command` messages. FSM-in-progress, button
callbacks, and free-text replies pass through untouched — by the time those
fire the user has already entered a flow via a command, which the gate has
already evaluated. If a toggle is flipped mid-flow, the user simply finishes
their current step; the next command entry will see the new gate.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from src.bot.strings import t
from src.core.db import get_session
from src.services.app_settings import SettingsSnapshot, get_settings

# Map: bare command name (no leading "/") → required toggle attribute.
# Anything not in this map is always-allowed (e.g. /h, /salary, /settings).
_LEGACY = "legacy_clock_inout_enabled"
_SITES = "sites_enabled"
_GEOFENCE = "geofence_enabled"
_CREWS = "crews_enabled"

COMMAND_FEATURE_MAP: dict[str, str] = {
    # Clock-in/out shift flow + everything that operates on shifts.
    "quick_start": _LEGACY,
    "my_open": _LEGACY,
    "today": _LEGACY,
    "me_yesterday": _LEGACY,
    "week": _LEGACY,
    "month": _LEGACY,
    "me": _LEGACY,
    "export": _LEGACY,
    "work_stats": _LEGACY,
    "site_stats": _LEGACY,
    "active": _LEGACY,
    "shifts": _LEGACY,
    "shift_info": _LEGACY,
    "shift_photos": _LEGACY,
    "edit_shift": _LEGACY,
    "delete_shift": _LEGACY,
    "restore_shift": _LEGACY,
    "note": _LEGACY,
    "work_type": _LEGACY,
    "stop_for": _LEGACY,
    "audit": _LEGACY,
    "break_start": _LEGACY,
    "break_stop": _LEGACY,
    "break_status": _LEGACY,
    "add_break": _LEGACY,
    "edit_break": _LEGACY,
    "delete_break": _LEGACY,
    # Per-site CRUD.
    "sites": _SITES,
    "site_info": _SITES,
    "sites_archive": _SITES,
    "set_site_rate": _SITES,
    "archive_site": _SITES,
    "unarchive_site": _SITES,
    "rename_site": _SITES,
    # Geofence (also implies sites, but the toggle is dedicated).
    "geofence_set": _GEOFENCE,
    "geofence_save": _GEOFENCE,
    "geofence_cancel": _GEOFENCE,
    "geofence_clear": _GEOFENCE,
    # Crew membership and crew-scoped reports.
    "invite": _CREWS,
    "join": _CREWS,
    "crew": _CREWS,
    "remove_member": _CREWS,
    "leave_crew": _CREWS,
    "add_foreman": _CREWS,
    "transfer_crew": _CREWS,
    "foremen": _CREWS,
    "crew_today": _CREWS,
    "crew_week": _CREWS,
    "crew_month": _CREWS,
    "crew_export": _CREWS,
    "crew_open": _CREWS,
    "crew_rates": _CREWS,
    "crew_shifts": _CREWS,
    "set_crew_rate": _CREWS,
    "crew_advances": _CREWS,
    "crew_salary": _CREWS,
}


def _extract_command_name(text: str | None) -> str | None:
    """Return the bare command name from a message text, or None."""
    if not text or not text.startswith("/"):
        return None
    # Strip leading "/", drop any "@botname" suffix, take the first token.
    head = text.split()[0][1:]
    if "@" in head:
        head = head.split("@", 1)[0]
    return head or None


def required_feature(command: str) -> str | None:
    """Return the toggle key required for the command, or None if always allowed."""
    return COMMAND_FEATURE_MAP.get(command)


def is_allowed(command: str, snap: SettingsSnapshot) -> bool:
    """True if the command is allowed given the current snapshot."""
    feature = required_feature(command)
    if feature is None:
        return True
    return bool(getattr(snap, feature, False))


class FeatureGateMiddleware(BaseMiddleware):
    """Block disabled `/command` entry points with a polite reply."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        if not isinstance(event, Message):
            return await handler(event, data)
        command = _extract_command_name(event.text)
        if command is None:
            return await handler(event, data)
        if required_feature(command) is None:
            return await handler(event, data)
        snap: SettingsSnapshot | None = None
        async for session in get_session():
            snap = await get_settings(session)
            await session.commit()
        if snap is not None and not is_allowed(command, snap):
            await event.answer(t("feature_disabled"))
            return None
        return await handler(event, data)
