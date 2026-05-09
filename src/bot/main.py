"""Bot entry point — dispatcher setup, long polling."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, TelegramObject

from src.bot.handlers import common, exports, reports, shifts
from src.bot.scheduler_runner import run_scheduler
from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import dispose_engine, init_engine

logger = structlog.get_logger()


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_tg_id: int) -> None:
        self.owner_tg_id = owner_tg_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        if (
            isinstance(event, Message)
            and event.from_user
            and event.from_user.id != self.owner_tg_id
        ):
            await event.answer(t("private_bot"))
            return None
        return await handler(event, data)


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

    dp.message.middleware(OwnerOnlyMiddleware(settings.owner_tg_id))

    dp.include_router(common.router)
    dp.include_router(shifts.router)
    dp.include_router(reports.router)
    dp.include_router(exports.router)

    logger.info("bot_starting", owner_tg_id=settings.owner_tg_id)

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
