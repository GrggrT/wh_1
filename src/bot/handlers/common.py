"""Common handlers: /start, /help, /cancel."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu
from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.app_settings import SettingsSnapshot, get_settings

router = Router()


def _role(db_user: User | None) -> str:
    return db_user.role if db_user else "worker"


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
    user_name = message.from_user.full_name if message.from_user else "User"
    await message.answer(
        t("welcome", name=user_name), reply_markup=main_menu(_role(db_user)),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    async for session in get_session():
        snap = await get_settings(session)
        await session.commit()
    await message.answer(_compose_help(snap))


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    await state.clear()
    await message.answer(t("cancelled"), reply_markup=main_menu(_role(db_user)))
