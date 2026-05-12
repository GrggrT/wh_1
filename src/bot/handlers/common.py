"""Common handlers: /start, /help, /cancel, /menu + reply-keyboard text buttons."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.handlers.accounting import cmd_cash, cmd_period
from src.bot.handlers.calendar import cmd_calendar
from src.bot.handlers.day_entries import cmd_h, cmd_my_days
from src.bot.handlers.onboarding import start_wizard
from src.bot.keyboards import simple_menu
from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.app_settings import SettingsSnapshot, get_settings

router = Router()


def _role(db_user: User | None) -> str:
    return db_user.role if db_user else "worker"


async def _snapshot() -> SettingsSnapshot:
    async for session in get_session():
        snap = await get_settings(session)
        await session.commit()
    return snap


def _compose_help(snap: SettingsSnapshot) -> str:
    parts = [t("help_core")]
    if snap.legacy_clock_inout_enabled:
        parts.append(t("help_section_legacy"))
    if snap.sites_enabled:
        parts.append(t("help_section_sites"))
    if snap.geofence_enabled:
        parts.append(t("help_section_geofence"))
    if snap.crews_enabled:
        parts.append(t("help_section_crews"))
    return "".join(parts)


@router.message(Command("start"))
async def cmd_start(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    await state.clear()
    if db_user is not None and db_user.onboarded_at is None:
        await start_wizard(message, state, db_user)
        return
    snap = await _snapshot()
    user_name = message.from_user.full_name if message.from_user else "User"
    await message.answer(
        t("welcome", name=user_name),
        reply_markup=simple_menu(snap, _role(db_user)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    snap = await _snapshot()
    await message.answer(_compose_help(snap))


@router.message(Command("menu"))
async def cmd_menu(
    message: Message, db_user: User | None = None,
) -> None:
    snap = await _snapshot()
    await message.answer(
        t("menu_hint"), reply_markup=simple_menu(snap, _role(db_user)),
    )


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    await state.clear()
    snap = await _snapshot()
    await message.answer(
        t("cancelled"), reply_markup=simple_menu(snap, _role(db_user)),
    )


# --- Reply-keyboard text buttons -> dispatch to existing handlers ----------
# These mirror the buttons rendered by `simple_menu` in keyboards.py.


def _noargs() -> CommandObject:
    return CommandObject(prefix="/", command="", args=None)


@router.message(F.text == t("menu_btn_hours"))
async def btn_hours(message: Message, db_user: User | None = None) -> None:
    await cmd_h(message, _noargs(), db_user=db_user)


@router.message(F.text == t("menu_btn_my_days"))
async def btn_my_days(message: Message, db_user: User | None = None) -> None:
    await cmd_my_days(message, db_user=db_user)


@router.message(F.text == t("menu_btn_period"))
async def btn_period(message: Message, db_user: User | None = None) -> None:
    await cmd_period(message, _noargs(), db_user=db_user)


@router.message(F.text == t("menu_btn_cash"))
async def btn_cash(message: Message, db_user: User | None = None) -> None:
    await cmd_cash(message, _noargs(), db_user=db_user)


@router.message(F.text == t("menu_btn_calendar"))
async def btn_calendar(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    await cmd_calendar(message, state, db_user=db_user)
