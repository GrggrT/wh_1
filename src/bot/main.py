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

from src.bot.handlers import (
    admin,
    advances,
    breaks,
    common,
    crew_admin,
    day_entries,
    exports,
    geofence_edit,
    notes,
    reports,
    shift_edits,
    shifts,
    system,
)
from src.bot.scheduler_runner import run_scheduler
from src.bot.strings import t
from src.core.config import Settings, get_settings
from src.core.db import dispose_engine, get_session, init_engine
from src.core.sentry import capture_exception, init_sentry
from src.services.crews import ROLE_OWNER, ensure_owner_role
from src.services.shifts import ensure_user


async def _run_uvicorn(
    settings: Settings,
    bot: Bot | None = None,
    dispatcher: Dispatcher | None = None,
) -> None:
    """Serve the FastAPI app (admin + optional webhook) on settings.admin_port."""
    import uvicorn

    from src.admin.app import create_app

    webhook_enabled = bool(settings.webhook_url and settings.webhook_secret)
    app = create_app(
        bot=bot if webhook_enabled else None,
        dispatcher=dispatcher if webhook_enabled else None,
        webhook_path=settings.webhook_path if webhook_enabled else None,
        webhook_secret=settings.webhook_secret if webhook_enabled else None,
    )
    config = uvicorn.Config(
        app,
        host=settings.admin_host,
        port=settings.admin_port,
        log_level=settings.log_level.lower(),
        access_log=False,
    )
    server = uvicorn.Server(config)
    await server.serve()

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
    BotCommand(command="h", description="Поставить часы за сегодня: /h 8"),
    BotCommand(command="my_days", description="Мои последние 14 дней"),
    BotCommand(command="edit_day", description="Изменить день: /edit_day YYYY-MM-DD <часы>"),
    BotCommand(command="remind_on", description="Включить вечернее напоминание: /remind_on HH"),
    BotCommand(command="remind_off", description="Отключить вечернее напоминание"),
    BotCommand(command="advance", description="Записать аванс: /advance <tg_id> <сумма>"),
    BotCommand(command="my_advances", description="Мои авансы"),
    BotCommand(command="crew_advances", description="Авансы бригады"),
    BotCommand(command="salary", description="Зарплата за месяц"),
    BotCommand(command="crew_salary", description="Зарплата бригады"),
    BotCommand(command="today", description="Смены за сегодня"),
    BotCommand(command="me_yesterday", description="Мои смены за вчера"),
    BotCommand(command="quick_start", description="Быстрый старт смены (последний объект)"),
    BotCommand(command="week", description="Смены за неделю"),
    BotCommand(command="month", description="Смены за месяц"),
    BotCommand(command="me", description="Мой месяц: /me YYYY-MM"),
    BotCommand(command="export", description="Выгрузка в Excel: /export YYYY-MM"),
    BotCommand(command="join", description="Присоединиться к бригаде: /join <код>"),
    BotCommand(command="invite", description="Код приглашения (для бригадира)"),
    BotCommand(command="crew", description="Состав бригады"),
    BotCommand(command="remove_member", description="Вывести работника из бригады"),
    BotCommand(command="crew_today", description="Бригада за сегодня"),
    BotCommand(command="crew_week", description="Бригада за неделю"),
    BotCommand(command="crew_month", description="Бригада за месяц"),
    BotCommand(command="crew_export", description="Экспорт бригады: /crew_export YYYY-MM"),
    BotCommand(command="add_foreman", description="Назначить бригадира (владелец)"),
    BotCommand(command="transfer_crew", description="Перевести работника (владелец)"),
    BotCommand(command="foremen", description="Список бригадиров (владелец)"),
    BotCommand(command="crew_open", description="Кто сейчас на смене (бригадир)"),
    BotCommand(command="crew_rates", description="Ставки бригады (бригадир)"),
    BotCommand(command="set_rate", description="Установить ставку: /set_rate <tg_id> <ставка>"),
    BotCommand(command="set_crew_rate", description="Ставка бригады по умолчанию"),
    BotCommand(command="my_rate", description="Моя ставка"),
    BotCommand(command="break_start", description="Начать перерыв"),
    BotCommand(command="break_stop", description="Завершить перерыв"),
    BotCommand(command="break_status", description="Статус текущего перерыва"),
    BotCommand(command="add_break", description="Добавить перерыв (бригадир/владелец)"),
    BotCommand(command="edit_break", description="Изменить перерыв (бригадир/владелец)"),
    BotCommand(command="delete_break", description="Удалить перерыв (бригадир/владелец)"),
    BotCommand(command="shifts", description="Последние смены"),
    BotCommand(command="crew_shifts", description="Последние смены бригады (бригадир)"),
    BotCommand(command="edit_shift", description="Изменить смену (бригадир/владелец)"),
    BotCommand(command="delete_shift", description="Удалить смену (бригадир/владелец)"),
    BotCommand(command="note", description="Заметка к открытой смене"),
    BotCommand(command="work_type", description="Тип работ для открытой смены"),
    BotCommand(command="stop_for", description="Закрыть смену работника (бригадир)"),
    BotCommand(command="audit", description="История изменений смены (бригадир)"),
    BotCommand(command="admin_audit", description="Журнал админ-действий (владелец)"),
    BotCommand(command="shift_info", description="Детали смены: /shift_info <id>"),
    BotCommand(command="shift_photos", description="Фото смены: /shift_photos <id>"),
    BotCommand(command="restore_shift", description="Восстановить удалённую (владелец)"),
    BotCommand(command="sites", description="Список объектов"),
    BotCommand(command="site_info", description="Детали объекта (бригадир/владелец)"),
    BotCommand(command="sites_archive", description="Архивные объекты"),
    BotCommand(command="set_site_rate", description="Ставка объекта: /set_site_rate <id> <ставка>"),
    BotCommand(command="archive_site", description="Архивировать объект: /archive_site <id>"),
    BotCommand(command="unarchive_site", description="Вернуть объект из архива"),
    BotCommand(command="rename_site", description="Переименовать объект"),
    BotCommand(command="geofence_set", description="Задать границу объекта: /geofence_set <id>"),
    BotCommand(command="geofence_save", description="Сохранить границу"),
    BotCommand(command="geofence_cancel", description="Отменить ввод границы"),
    BotCommand(command="geofence_clear", description="Удалить границу: /geofence_clear <id>"),
    BotCommand(command="whoami", description="Кто я и в какой бригаде"),
    BotCommand(command="my_open", description="Моя текущая открытая смена"),
    BotCommand(command="leave_crew", description="Выйти из бригады"),
    BotCommand(command="status", description="Статус бота (владелец)"),
    BotCommand(command="active", description="Все открытые смены (владелец)"),
    BotCommand(command="stats", description="Глобальная статистика (владелец)"),
    BotCommand(command="work_stats", description="Часы по типам работ за месяц (владелец)"),
    BotCommand(command="site_stats", description="Часы по объектам за месяц (владелец)"),
    BotCommand(command="digest", description="Сводка дня (владелец)"),
    BotCommand(command="digest_week", description="Сводка прошлой недели (владелец)"),
    BotCommand(command="digest_month", description="Сводка месяца (владелец)"),
    BotCommand(command="cancel", description="Отмена текущего действия"),
]


async def _publish_bot_commands(bot: Bot) -> None:
    try:
        await bot.set_my_commands(_BOT_COMMANDS)
    except TelegramAPIError:
        logger.warning("set_my_commands_failed")


def _register_error_handler(dp: Dispatcher, bot: Bot, settings: Settings) -> None:
    """Catch all uncaught handler errors: reply to user, alert owner, log."""

    @dp.errors()
    async def handle_error(event: Any) -> bool:  # noqa: ANN401
        update = getattr(event, "update", None)
        exception = getattr(event, "exception", None)
        update_id = getattr(update, "update_id", "?") if update else "?"
        logger.exception(
            "handler_error",
            update_id=update_id,
            exc_info=exception,
        )
        if isinstance(exception, BaseException):
            capture_exception(exception)
        message: Message | None = None
        if update is not None:
            message = getattr(update, "message", None)
        if message is not None:
            with contextlib.suppress(TelegramAPIError):
                await message.answer(t("internal_error"))
        with contextlib.suppress(TelegramAPIError):
            await bot.send_message(
                settings.owner_tg_id,
                t(
                    "owner_error_alert",
                    error=str(exception)[:300],
                    update_id=str(update_id),
                ),
                parse_mode="HTML",
            )
        return True


async def main() -> None:
    settings = get_settings()

    import logging

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    if init_sentry(settings):
        logger.info("sentry_enabled", environment=settings.sentry_environment)

    init_engine(settings)

    bot = Bot(token=settings.bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.message.middleware(UserResolveMiddleware(settings.owner_tg_id))

    dp.include_router(common.router)
    dp.include_router(system.router)
    dp.include_router(admin.router)
    dp.include_router(crew_admin.router)
    dp.include_router(shifts.router)
    dp.include_router(breaks.router)
    dp.include_router(shift_edits.router)
    dp.include_router(geofence_edit.router)
    dp.include_router(notes.router)
    dp.include_router(reports.router)
    dp.include_router(exports.router)
    dp.include_router(day_entries.router)
    dp.include_router(advances.router)

    _register_error_handler(dp, bot, settings)

    logger.info("bot_starting", owner_tg_id=settings.owner_tg_id)

    await _publish_bot_commands(bot)
    scheduler_task = asyncio.create_task(run_scheduler(bot, settings))

    webhook_enabled = bool(settings.webhook_url and settings.webhook_secret)
    serve_http = settings.admin_password or webhook_enabled

    http_task: asyncio.Task[None] | None = None
    if serve_http:
        if webhook_enabled:
            logger.info(
                "webhook_starting",
                url=settings.webhook_url,
                path=settings.webhook_path,
            )
            full_url = settings.webhook_url.rstrip("/") + settings.webhook_path
            with contextlib.suppress(TelegramAPIError):
                await bot.set_webhook(
                    url=full_url,
                    secret_token=settings.webhook_secret,
                    drop_pending_updates=False,
                )
        if settings.admin_password:
            logger.info("admin_panel_starting", port=settings.admin_port)
        http_task = asyncio.create_task(_run_uvicorn(settings, bot, dp))

    try:
        if webhook_enabled:
            # Wait until uvicorn task ends (Ctrl-C / shutdown).
            assert http_task is not None
            await http_task
        else:
            await dp.start_polling(bot)
    finally:
        if webhook_enabled:
            with contextlib.suppress(TelegramAPIError):
                await bot.delete_webhook(drop_pending_updates=False)
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        if http_task is not None and not http_task.done():
            http_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await http_task
        await dispose_engine()
        await bot.session.close()


def run() -> None:
    asyncio.run(main())


if __name__ == "__main__":
    run()
