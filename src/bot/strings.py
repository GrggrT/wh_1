"""All user-facing strings. Russian only in Phase 0, structured for future i18n."""

from typing import Final

STRINGS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "welcome": "Привет, {name}! Я бот для учёта рабочего времени на стройке.",
        "help": (
            "Команды:\n"
            "/start — начало работы\n"
            "/help — справка\n"
            "/today — смены за сегодня\n"
            "/week — смены за неделю\n"
            "/month — смены за месяц\n"
            "/export YYYY-MM — выгрузка в Excel\n"
            "/cancel — отмена текущего действия"
        ),
        "private_bot": "Это приватный бот.",
        "shift_already_open": (
            "У тебя уже открыта смена с {start_time} на {site}. Сначала закрой её."
        ),
        "select_site": "Выбери объект:",
        "new_site": "Новый объект",
        "enter_site_name": "Введи название нового объекта:",
        "send_location": "Отправь геолокацию",
        "location_outside_warning": "Локация вне границ объекта, но смена начата.",
        "shift_started": "Смена начата в {time} на объекте «{site}».",
        "send_photo_or_skip": "Отправь фото или нажми «Пропустить».",
        "skip": "Пропустить",
        "photo_saved": "Фото сохранено.",
        "no_open_shift": "Нет открытой смены.",
        "confirm_stop": "Закрыть смену на «{site}»? Начало: {start_time}.",
        "confirm": "Подтвердить",
        "cancel_btn": "Отмена",
        "send_end_location": "Отправь геолокацию завершения.",
        "shift_stopped": "Смена закрыта. {hours} ч. на объекте «{site}».",
        "shift_stopped_with_amount": (
            "Смена закрыта. {hours} ч. на объекте «{site}». Сумма: {amount} zl."
        ),
        "cancelled": "Действие отменено.",
        "no_shifts_today": "Сегодня смен не было.",
        "no_shifts_week": "На этой неделе смен не было.",
        "no_shifts_month": "В этом месяце смен не было.",
        "today_summary": "Сегодня: {hours} ч. ({count} смен)",
        "week_summary": "Неделя: {hours} ч. ({count} смен)",
        "month_summary": "Месяц: {hours} ч. ({count} смен)",
        "export_empty": "Нет данных за {period}.",
        "export_ready": "Выгрузка за {period} готова.",
        "start_shift_btn": "Начать смену",
        "stop_shift_btn": "Закончить смену",
        "integrity_error": "Не удалось — уже есть открытая смена. /cancel",
        "error_generic": "Произошла ошибка. Попробуй позже.",
        "site_created": "Объект «{name}» создан.",
        "shift_reminder": (
            "Смена идёт уже {hours} ч. Не забудь её закрыть, когда закончишь."
        ),
        "shift_auto_closed": (
            "Смена автоматически закрыта (превышен лимит). Часы: {hours}. "
            "При необходимости поправь вручную."
        ),
    },
}


def t(key: str, locale: str = "ru", **kwargs: object) -> str:
    template = STRINGS.get(locale, STRINGS["ru"]).get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
