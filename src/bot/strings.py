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
            "/join <код> — присоединиться к бригаде\n"
            "/invite — выдать код (для бригадира)\n"
            "/crew — состав бригады (для бригадира)\n"
            "/add_foreman <tg_id> [название] — назначить бригадира (владелец)\n"
            "/foremen — список бригадиров (владелец)\n"
            "/crew_today /crew_week /crew_month — отчёты по бригаде\n"
            "/crew_export YYYY-MM — Excel по бригаде\n"
            "/crew_open — кто сейчас на смене\n"
            "/crew_rates — ставки бригады\n"
            "/sites — список объектов\n"
            "/set_rate <tg_id> <ставка> — ставка работника\n"
            "/set_site_rate <site_id> <ставка> — ставка объекта\n"
            "/archive_site <site_id> — архивировать объект\n"
            "/whoami — кто я / /my_rate — моя ставка\n"
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
        "crew_today_btn": "Бригада сегодня",
        "invite_btn": "Пригласить",
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
        "not_authorized": "Команда недоступна.",
        "add_foreman_usage": "Используй: /add_foreman <tg_id> [название бригады]",
        "user_not_seen": (
            "Пользователь не найден. Сначала он должен написать боту /start."
        ),
        "foreman_added": "Бригадир назначен. Бригада: «{crew}».",
        "foremen_empty": "Бригадиров пока нет.",
        "foremen_list": "Бригадиры:\n{body}",
        "no_crew": "У тебя ещё нет бригады.",
        "invite_issued": (
            "Код приглашения: {code}\n"
            "Действует 72 часа. Перешли работнику — он напишет боту: /join {code}"
        ),
        "crew_empty": "В бригаде «{crew}» пока никого.",
        "crew_list": "Бригада «{crew}»:\n{body}",
        "join_usage": "Используй: /join <код>",
        "invite_error": "Не получилось присоединиться: {reason}.",
        "joined_crew": "Ты в бригаде «{crew}». Удачной смены!",
        "crew_no_shifts_today": "По бригаде сегодня смен нет.",
        "crew_no_shifts_week": "По бригаде на этой неделе смен нет.",
        "crew_no_shifts_month": "По бригаде в этом месяце смен нет.",
        "crew_today_summary": (
            "Бригада сегодня:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_week_summary": (
            "Бригада за неделю:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_month_summary": (
            "Бригада за месяц:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_export_usage": "Используй: /crew_export YYYY-MM",
        "whoami": (
            "Кто ты:\n"
            "Имя: {name}\n"
            "Telegram ID: {tg_id}\n"
            "Роль: {role}\n"
            "Бригада: {crew}\n"
            "Ставка: {rate}"
        ),
        "status": (
            "Статус:\n"
            "Uptime: {uptime}\n"
            "Запуск: {started}\n"
            "База данных: {db}"
        ),
        "crew_open_none": "В бригаде «{crew}» сейчас никто не на смене.",
        "crew_open_summary": "Бригада «{crew}» сейчас на смене:\n{body}",
        "crew_open_row": "• {name} — «{site}», с {start} ({hours} ч)",
        "internal_error": (
            "Что-то пошло не так. Я уже сообщил владельцу. Попробуй ещё раз позже."
        ),
        "owner_error_alert": (
            "\u26a0 Ошибка в обработчике:\n<code>{error}</code>\n\nUpdate id: {update_id}"
        ),
        "set_rate_usage": "Используй: /set_rate <tg_id> <ставка>",
        "rate_invalid": "Ставка должна быть неотрицательным числом.",
        "rate_set": "Ставка для {name} установлена: {rate} zł/ч.",
        "rate_not_set": "У тебя не задана ставка. Попроси бригадира — /set_rate.",
        "my_rate": "Твоя ставка: {rate} zł/ч.",
        "sites_empty": "Объектов пока нет. Создай первый при старте смены.",
        "sites_list": "Объекты:\n{body}",
        "site_not_found": "Объект не найден или не принадлежит тебе.",
        "set_site_rate_usage": "Используй: /set_site_rate <site_id> <ставка>",
        "site_rate_set": "Ставка для «{name}» установлена: {rate} zł/ч.",
        "archive_site_usage": "Используй: /archive_site <site_id>",
        "site_archived": "Объект «{name}» переведён в архив.",
        "crew_rates_list": "Ставки в бригаде «{crew}»:\n{body}",
    },
}


def t(key: str, locale: str = "ru", **kwargs: object) -> str:
    template = STRINGS.get(locale, STRINGS["ru"]).get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
