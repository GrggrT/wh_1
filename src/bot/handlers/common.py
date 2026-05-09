"""Common handlers: /start, /help, /cancel."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from src.bot.keyboards import main_menu
from src.bot.strings import t
from src.core.models import User

router = Router()


def _role(db_user: User | None) -> str:
    return db_user.role if db_user else "worker"


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
    await message.answer(t("help"))


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    await state.clear()
    await message.answer(t("cancelled"), reply_markup=main_menu(_role(db_user)))
