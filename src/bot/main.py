"""Bot entry point — dispatcher setup, long polling."""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.exceptions import TelegramAPIError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message, TelegramObject

from src.bot.handlers import (
    accounting,
    admin,
    advances,
    backup,
    breaks,
    common,
    crew_admin,
    day_entries,
    exports,
    geofence_edit,
    nl_router,
    notes,
    onboarding,
    profile,
    report,
    reports,
    shift_edits,
    shifts,
    system,
)
from src.bot.handlers import (
    calendar as calendar_handler,
)
from src.bot.handlers import (
    settings as settings_handler,
)
from src.bot.middlewares.features import FeatureGateMiddleware
from src.bot.middlewares.fsm_breadcrumbs import FSMBreadcrumbMiddleware
from src.bot.scheduler_runner import run_scheduler, run_webhook_healer
from src.bot.strings import t
from src.core.config import Settings, get_settings
from src.core.db import dispose_engine, get_session, init_engine
from src.core.sentry import capture_exception, init_sentry
from src.services.app_settings import SettingsSnapshot
from src.services.app_settings import get_settings as get_app_settings
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
    """Resolve the DB user for each incoming Message/CallbackQuery and inject it.

    Bootstraps the configured owner_tg_id as role='owner' on first contact.
    Without this, callback-query handlers that take ``db_user`` would receive
    None and silently no-op (inline buttons appear to do nothing).
    """

    def __init__(self, owner_tg_id: int) -> None:
        self.owner_tg_id = owner_tg_id

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        if not isinstance(event, Message | CallbackQuery):
            return await handler(event, data)
        tg_user = event.from_user
        if tg_user is None:
            return await handler(event, data)
        async for session in get_session():
            user = await ensure_user(
                session, tg_user.id, tg_user.full_name,
            )
            if tg_user.id == self.owner_tg_id and user.role != ROLE_OWNER:
                await ensure_owner_role(session, self.owner_tg_id)
            await session.commit()
        data["db_user"] = user
        return await handler(event, data)


# Bot commands are split into groups so the visible command menu shrinks to
# the simple-mode core by default. Advanced groups are appended only when the
# matching toggle is on (see compose_bot_commands). Handler routers stay
# registered regardless — typing the command still works.

_CORE_COMMANDS: list[BotCommand] = [
    BotCommand(command="start", description="Начало работы"),
    BotCommand(command="help", description="Справка"),
    BotCommand(command="menu", description="Главное меню"),
    BotCommand(command="h", description="Поставить часы за сегодня: /h 8"),
    BotCommand(command="calendar", description="Календарь — редактировать любую дату"),
    BotCommand(command="period", description="Расчёт за период (часы + выплаты)"),
    BotCommand(command="cash", description="Денежный поток за месяц"),
    BotCommand(command="owed", description="Что ещё не выплачено"),
    BotCommand(command="forecast", description="Прогноз до конца месяца"),
    BotCommand(command="range", description="Сумма за период: /range YYYY-MM-DD YYYY-MM-DD"),
    BotCommand(command="report", description="Отчёт за N месяцев: /report [N]"),
    BotCommand(command="export_archive", description="ZIP-архив отчёта (XLSX+PDF+PNG)"),
    BotCommand(command="backup", description="Скачать резервную копию данных"),
    BotCommand(command="restore", description="Восстановить из .xlsx-бэкапа"),
    BotCommand(
        command="share_backup",
        description="Одноразовый код для переноса",
    ),
    BotCommand(
        command="restore_from",
        description="Принять данные по коду",
    ),
    BotCommand(
        command="backup_to_cloud",
        description="Сохранить бэкап в облако",
    ),
    BotCommand(
        command="restore_from_cloud",
        description="Восстановить бэкап из облака",
    ),
    BotCommand(command="my_days", description="Мои последние 14 дней"),
    BotCommand(command="profile", description="Профиль: имя, ставка, валюта, напоминание"),
    BotCommand(command="my_rate", description="Моя ставка"),
    BotCommand(command="remind_on", description="Вечернее напоминание: /remind_on HH"),
    BotCommand(command="remind_off", description="Отключить напоминание"),
    BotCommand(command="whoami", description="Кто я"),
    BotCommand(command="cancel", description="Отмена текущего действия"),
]

# Owner extras. Single-user bot, so this stays tiny — money-entry commands
# live inside /calendar now.
_OWNER_COMMANDS: list[BotCommand] = [
    BotCommand(command="settings", description="Настройки бота"),
    BotCommand(command="set_rate", description="Ставка: /set_rate <tg_id> <ставка>"),
    BotCommand(command="status", description="Статус бота"),
    BotCommand(command="stats", description="Глобальная статистика"),
]

_LEGACY_SHIFTS_COMMANDS: list[BotCommand] = [
    BotCommand(command="quick_start", description="Быстрый старт смены"),
    BotCommand(command="my_open", description="Моя открытая смена"),
    BotCommand(command="today", description="Смены за сегодня"),
    BotCommand(command="me_yesterday", description="Мои смены за вчера"),
    BotCommand(command="week", description="Смены за неделю"),
    BotCommand(command="month", description="Смены за месяц"),
    BotCommand(command="me", description="Мой месяц: /me YYYY-MM"),
    BotCommand(command="export", description="Выгрузка в Excel: /export YYYY-MM"),
    BotCommand(command="shifts", description="Последние смены"),
    BotCommand(command="shift_info", description="Детали смены: /shift_info <id>"),
    BotCommand(command="shift_photos", description="Фото смены: /shift_photos <id>"),
    BotCommand(command="edit_shift", description="Изменить смену"),
    BotCommand(command="delete_shift", description="Удалить смену"),
    BotCommand(command="restore_shift", description="Восстановить удалённую (владелец)"),
    BotCommand(command="note", description="Заметка к открытой смене"),
    BotCommand(command="work_type", description="Тип работ для открытой смены"),
    BotCommand(command="stop_for", description="Закрыть смену работника (бригадир)"),
    BotCommand(command="audit", description="История изменений смены"),
    BotCommand(command="admin_audit", description="Журнал админ-действий (владелец)"),
    BotCommand(command="active", description="Все открытые смены (владелец)"),
    BotCommand(command="break_start", description="Начать перерыв"),
    BotCommand(command="break_stop", description="Завершить перерыв"),
    BotCommand(command="break_status", description="Статус текущего перерыва"),
    BotCommand(command="add_break", description="Добавить перерыв"),
    BotCommand(command="edit_break", description="Изменить перерыв"),
    BotCommand(command="delete_break", description="Удалить перерыв"),
    BotCommand(command="work_stats", description="Часы по типам работ за месяц"),
    BotCommand(command="digest_week", description="Сводка прошлой недели"),
    BotCommand(command="digest_month", description="Сводка месяца"),
]

_SITES_COMMANDS: list[BotCommand] = [
    BotCommand(command="sites", description="Список объектов"),
    BotCommand(command="site_info", description="Детали объекта"),
    BotCommand(command="sites_archive", description="Архивные объекты"),
    BotCommand(command="set_site_rate", description="Ставка объекта"),
    BotCommand(command="archive_site", description="Архивировать объект"),
    BotCommand(command="unarchive_site", description="Вернуть из архива"),
    BotCommand(command="rename_site", description="Переименовать объект"),
    BotCommand(command="site_stats", description="Часы по объектам за месяц"),
]

_GEOFENCE_COMMANDS: list[BotCommand] = [
    BotCommand(command="geofence_set", description="Задать границу объекта"),
    BotCommand(command="geofence_save", description="Сохранить границу"),
    BotCommand(command="geofence_cancel", description="Отменить ввод границы"),
    BotCommand(command="geofence_clear", description="Удалить границу"),
]

_CREWS_COMMANDS: list[BotCommand] = [
    BotCommand(command="join", description="Присоединиться: /join <код>"),
    BotCommand(command="invite", description="Код приглашения (бригадир)"),
    BotCommand(command="crew", description="Состав бригады"),
    BotCommand(command="remove_member", description="Вывести из бригады"),
    BotCommand(command="leave_crew", description="Выйти из бригады"),
    BotCommand(command="add_foreman", description="Назначить бригадира (владелец)"),
    BotCommand(command="transfer_crew", description="Перевести работника (владелец)"),
    BotCommand(command="foremen", description="Список бригадиров (владелец)"),
    BotCommand(command="crew_today", description="Бригада за сегодня"),
    BotCommand(command="crew_week", description="Бригада за неделю"),
    BotCommand(command="crew_month", description="Бригада за месяц"),
    BotCommand(command="crew_export", description="Экспорт бригады"),
    BotCommand(command="crew_open", description="Кто сейчас на смене"),
    BotCommand(command="crew_rates", description="Ставки бригады"),
    BotCommand(command="set_crew_rate", description="Ставка бригады по умолчанию"),
    BotCommand(command="crew_shifts", description="Последние смены бригады"),
    BotCommand(command="crew_advances", description="Авансы бригады"),
    BotCommand(command="crew_salary", description="Зарплата бригады"),
]


def compose_bot_commands(snap: SettingsSnapshot) -> list[BotCommand]:
    """Build the BotCommands list reflecting current product-mode toggles."""
    commands = list(_CORE_COMMANDS) + list(_OWNER_COMMANDS)
    if snap.legacy_clock_inout_enabled:
        commands += _LEGACY_SHIFTS_COMMANDS
    if snap.sites_enabled:
        commands += _SITES_COMMANDS
    if snap.geofence_enabled:
        commands += _GEOFENCE_COMMANDS
    if snap.crews_enabled:
        commands += _CREWS_COMMANDS
    return commands


async def _publish_bot_commands(bot: Bot) -> None:
    """Publish the slim set of BotCommands based on the current settings."""
    async for session in get_session():
        snap = await get_app_settings(session)
        await session.commit()
    try:
        await bot.set_my_commands(compose_bot_commands(snap))
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

    user_resolve = UserResolveMiddleware(settings.owner_tg_id)
    dp.message.middleware(user_resolve)
    dp.callback_query.middleware(user_resolve)
    dp.message.middleware(FeatureGateMiddleware())
    fsm_breadcrumbs = FSMBreadcrumbMiddleware()
    dp.message.middleware(fsm_breadcrumbs)
    dp.callback_query.middleware(fsm_breadcrumbs)

    dp.include_router(onboarding.router)
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
    dp.include_router(accounting.router)
    dp.include_router(profile.router)
    dp.include_router(report.router)
    dp.include_router(backup.router)
    dp.include_router(calendar_handler.router)
    dp.include_router(settings_handler.router)
    # NL dispatcher must stay last: it catches any leftover plain text
    # and forwards to /report, /period, /cash, /owed.
    dp.include_router(nl_router.router)

    _register_error_handler(dp, bot, settings)

    logger.info("bot_starting", owner_tg_id=settings.owner_tg_id)

    await _publish_bot_commands(bot)
    scheduler_task = asyncio.create_task(run_scheduler(bot, settings))

    webhook_enabled = bool(settings.webhook_url and settings.webhook_secret)
    healer_task: asyncio.Task[None] | None = (
        asyncio.create_task(run_webhook_healer(bot, settings))
        if webhook_enabled
        else None
    )
    serve_http = settings.admin_password or webhook_enabled

    http_task: asyncio.Task[None] | None = None
    if serve_http:
        if webhook_enabled:
            full_url = settings.webhook_url.strip().rstrip("/") + settings.webhook_path
            logger.info(
                "webhook_starting",
                full_url=full_url,
                path=settings.webhook_path,
            )
            try:
                await bot.set_webhook(
                    url=full_url,
                    secret_token=settings.webhook_secret,
                    drop_pending_updates=False,
                )
                info = await bot.get_webhook_info()
                logger.info(
                    "webhook_set_ok",
                    registered_url=info.url,
                    pending_update_count=info.pending_update_count,
                    last_error_message=info.last_error_message,
                )
            except TelegramAPIError:
                logger.exception("webhook_set_failed")
                raise
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
        # NOTE: do NOT call delete_webhook on shutdown. Railway rolling
        # deploys overlap old and new containers briefly; if the old one
        # deletes the webhook after the new one set it, Telegram has
        # nowhere to deliver updates and the bot silently goes offline.
        # Each container's startup overwrites the registered webhook, so
        # leaving the old registration in place is safe.
        scheduler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await scheduler_task
        if healer_task is not None:
            healer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await healer_task
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
