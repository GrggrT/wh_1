"""Lunch / pause break handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.breaks import (
    BreakError,
    start_break,
    stop_break,
)
from src.services.shifts import get_open_shift

router = Router()


@router.message(Command("break_start"))
async def cmd_break_start(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    start_time = ""
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        try:
            new_break = await start_break(session, shift)
        except BreakError as exc:
            if str(exc) == "already_on_break":
                await message.answer(t("already_on_break"))
            else:
                await message.answer(t("no_open_shift"))
            return
        start_time = new_break.start_at.strftime("%H:%M")
        await session.commit()
    await message.answer(t("break_started", time=start_time))


@router.message(Command("break_stop"))
async def cmd_break_stop(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    minutes = 0
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        try:
            closed = await stop_break(session, shift.id)
        except BreakError:
            await message.answer(t("no_open_break"))
            return
        assert closed.end_at is not None
        minutes = int((closed.end_at - closed.start_at).total_seconds() // 60)
        await session.commit()
    await message.answer(t("break_stopped", minutes=minutes))
