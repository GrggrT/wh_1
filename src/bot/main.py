"""Bot entry point — dispatcher setup, long polling."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, Message, TelegramObject

from src.bot.handlers import common, crew_admin, exports, reports, shifts
from src.bot.scheduler_runner import run_scheduler
from src.core.config import get_settings
from src.core.db import dispose_engine, get_session, init_engine
from src.services.crews import ROLE_OWNER, ensure_owner_role
from src.services.shifts import ensure_user

logger = structlog.get_logger()


class UserResolveMiddleware(BaseMiddleware):
    """Resolve the DB user for each incoming Message and inject it into data.

    Bootstraps the configured owner_tg_id as role='owner' on first contact.
    """

    def __init__(self, owner_tg_id: int) -> None:
        self.owner_tg_id = owner_tg_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        if not isinstance(event, Message) or event.from_user is None:
            return await handler(event, data)
        async for session in get_session():
            user = await ensure_user(
                session, event.from_user.id, event.from_user.full_name,
            )
            if event.from_user.id == self.owner_tg_id and user.role != ROLE_OWNER:
                await ensure_owner_role(session, self.owner_tg_id)
            await session.commit()
        data["db_user"] = user
        return await handler(event, data)


_BOT_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Начало работы"),
    BotCommand(command="help", description="Справка по командам"),
    BotCommand(command="today", description="Смены за сегодня"),
    BotCommand(command="week", description="Смены за неделю"),
    BotCommand(command="month", description="Смены за месяц"),
    BotCommand(command="export", description="Выгрузка в Excel: /export YYYY-MM"),
    BotCommand(command="join", description="Присоединиться к бригаде: /join <код>"),
    BotCommand(command="invite", description="Код приглашения (для бригадира)"),
    BotCommand(command="crew", description="Состав бригады"),
    BotCommand(command="crew_today", description="Бригада за сегодня"),
    BotCommand(command="crew_week", description="Бригада за неделю"),
    BotCommand(command="crew_month", description="Бригада за месяц"),
    BotCommand(command="crew_export", description="Экспорт бригады: /crew_export YYYY-MM"),
    BotCommand(command="add_foreman", description="Назначить бригадира (владелец)"),
    BotCommand(command="foremen", description="Список бригадиров (владелец)"),
    BotCommand(command="cancel", description="Отмена текущего действия"),
]


async def _publish_bot_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(_BOT_COMMANDS)
    except TelegramAPIError:
        logger.warning("set_my_commands_failed")


async def main() -> None:
    settings = get_settings()

    import logging

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    init_engine(settings)

    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(UserResolveMiddleware(settings.owner_tg_id))

    dp.include_router(common.router)
    dp.include_router(crew_admin.router)
    dp.include_router(shifts.router)
    dp.include_router(reports.router)
    dp.include_router(exports.router)

    logger.info("bot_starting", owner_tg_id=settings.owner_tg_id)

    await _publish_bot_commands(bot)
    scheduler_task = asyncio.create_task(run_scheduler(bot, settings))
    try:
        await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        await dispose_engine()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
