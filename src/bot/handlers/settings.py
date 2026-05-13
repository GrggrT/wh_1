"""Phase 5.4: /settings — owner-only inline menu to flip product-mode toggles."""

from __future__ import annotations

import contextlib

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.app_settings import (
    TOGGLE_KEYS,
    SettingsSnapshot,
    get_settings,
    toggle,
)
from src.services.crews import ROLE_OWNER

router = Router()

# Callback prefix; payload is the toggle key (see TOGGLE_KEYS).
_CB_TOGGLE = "st:"


def _is_owner(user: User | None) -> bool:
    return user is not None and user.role == ROLE_OWNER


def _label(key: str, value: bool) -> str:
    """Render a toggle button label like '✅ Объекты' / '⬜ Объекты'."""
    mark = "✅" if value else "⬜"
    name = t(f"settings_label_{key}")
    return f"{mark} {name}"


def _keyboard(snap: SettingsSnapshot) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key in TOGGLE_KEYS:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_label(key, bool(getattr(snap, key))),
                    callback_data=f"{_CB_TOGGLE}{key}",
                ),
            ],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _body(snap: SettingsSnapshot) -> str:
    return t("settings_header")


@router.message(Command("settings"))
async def cmd_settings(message: Message, db_user: User | None = None) -> None:
    if not _is_owner(db_user):
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        snap = await get_settings(session)
        await session.commit()
    await message.answer(
        _body(snap), reply_markup=_keyboard(snap), parse_mode="HTML",
    )


@router.callback_query(F.data.startswith(_CB_TOGGLE))
async def cb_toggle(query: CallbackQuery, db_user: User | None = None) -> None:
    if not _is_owner(db_user) or query.data is None:
        await query.answer(t("not_authorized"), show_alert=True)
        return
    key = query.data[len(_CB_TOGGLE) :]
    if key not in TOGGLE_KEYS:
        await query.answer()
        return
    async for session in get_session():
        snap = await toggle(session, key)
        await session.commit()
    if isinstance(query.message, Message):
        # Telegram may complain "message not modified"; ignore that.
        with contextlib.suppress(Exception):
            await query.message.edit_text(
                _body(snap), reply_markup=_keyboard(snap), parse_mode="HTML",
            )
    # Republish the BotCommands menu so the new toggle state is reflected
    # in the user's "/" autocomplete list right away.
    bot = query.bot
    if bot is not None:
        from src.bot.main import compose_bot_commands  # local import: avoid cycle

        with contextlib.suppress(TelegramAPIError):
            await bot.set_my_commands(compose_bot_commands(snap))
    await query.answer(t("settings_saved"))
