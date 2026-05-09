"""Common handlers: /start, /help, /cancel."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu
from src.bot.strings import t
from src.core.db import get_session
from src.services.shifts import ensure_user

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user_name = message.from_user.full_name if message.from_user else "User"
    async for session in get_session():
        assert message.from_user is not None
        await ensure_user(session, message.from_user.id, user_name)
        await session.commit()
    await message.answer(t("welcome", name=user_name), reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(t("help"))


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("cancelled"), reply_markup=main_menu())
