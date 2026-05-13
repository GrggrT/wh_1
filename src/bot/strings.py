"""All user-facing strings. Russian only in Phase 0, structured for future i18n."""

from typing import Final

STRINGS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "welcome": "Привет, <b>{name}</b>! Я бот для учёта рабочего времени на стройке.",
        "help": (
            "Команды:\n"
            "/start — начало работы\n"
            "/help — справка\n"
            "/h <часы> — поставить часы за сегодня (например: /h 8)\n"
            "/my_days — мои последние 14 дней\n"
            "/edit_day YYYY-MM-DD <часы> — изменить день\n"
            "/remind_on HH — вечернее напоминание поставить часы\n"
            "/remind_off — отключить напоминание\n"
            "/settings — настройки режима (владелец)\n"
            "/salary [YYYY-MM] — расчёт зарплаты\n"
            "/my_advances [YYYY-MM] — мои авансы\n"
            "/advance <tg_id> <сумма> — записать аванс (бригадир/владелец)\n"
            "/crew_advances [YYYY-MM] — авансы бригады (бригадир)\n"
            "/crew_salary [YYYY-MM] — зарплата бригады (бригадир)\n"
            "/today — смены за сегодня\n"
            "/me_yesterday — мои смены за вчера\n"
            "/quick_start — быстрый старт смены (последний объект)\n"
            "/week — смены за неделю\n"
            "/month — смены за месяц\n"
            "/me YYYY-MM — мой произвольный месяц\n"
            "/export YYYY-MM — выгрузка в Excel\n"
            "/join <код> — присоединиться к бригаде\n"
            "/invite — выдать код (для бригадира)\n"
            "/crew — состав бригады (для бригадира)\n"
            "/remove_member <tg_id> — вывести работника из бригады\n"
            "/add_foreman <tg_id> [название] — назначить бригадира (владелец)\n"
            "/transfer_crew <tg_id> <crew_id> — перевести работника (владелец)\n"
            "/foremen — список бригадиров (владелец)\n"
            "/crew_today /crew_week /crew_month — отчёты по бригаде\n"
            "/crew_export YYYY-MM — Excel по бригаде\n"
            "/crew_open — кто сейчас на смене\n"
            "/crew_rates — ставки бригады\n"
            "/sites — список объектов\n"
            "/site_info <id> — детали объекта (бригадир/владелец)\n"
            "/sites_archive — архивные объекты (бригадир/владелец)\n"
            "/set_rate <tg_id> <ставка> — ставка работника\n"
            "/set_crew_rate <ставка> — дефолтная ставка для бригады\n"
            "/set_site_rate <site_id> <ставка> — ставка объекта\n"
            "/archive_site <site_id> — архивировать объект\n"
            "/unarchive_site <site_id> — вернуть объект из архива\n"
            "/rename_site <site_id> <название> — переименовать объект\n"
            "/geofence_set <site_id> — задать границу объекта (точками)\n"
            "/geofence_save — сохранить введённую границу\n"
            "/geofence_cancel — отменить ввод границы\n"
            "/geofence_clear <site_id> — удалить границу объекта\n"
            "/whoami — кто я / /my_rate — моя ставка\n"
            "/my_open — моя открытая смена\n"
            "/leave_crew — выйти из бригады\n"
            "/break_start /break_stop /break_status — учёт перерыва\n"
            "/add_break <shift_id> <начало> <конец> — добавить перерыв (бригадир/владелец)\n"
            "/edit_break <break_id> start|end <время> — изменить перерыв\n"
            "/delete_break <break_id> — удалить перерыв\n"
            "/shifts — последние смены\n"
            "/crew_shifts — последние смены бригады (бригадир)\n"
            "/shift_info <id> — детали смены\n"
            "/shift_photos <id> — фото смены\n"
            "/edit_shift <id> <поле> <значение> — изменить смену (бригадир/владелец)\n"
            "/delete_shift <id> — удалить смену (бригадир/владелец)\n"
            "/restore_shift <audit_id> — восстановить удалённую смену (владелец)\n"
            "/note <текст> — заметка к открытой смене\n"
            "/work_type <тип> — тип работ для открытой смены\n"
            "/stop_for <tg_id> — закрыть смену работника (бригадир)\n"
            "/audit <id> — история изменений смены (бригадир)\n"
            "/admin_audit [N] — журнал админ-действий (владелец)\n"
            "/active — все открытые смены (владелец)\n"
            "/stats — глобальная статистика (владелец)\n"
            "/work_stats [YYYY-MM] — часы по типам работ за месяц (владелец)\n"
            "/site_stats [YYYY-MM] — часы по объектам за месяц (владелец)\n"
            "/digest — сводка дня (владелец)\n"
            "/digest_week — сводка прошлой недели (владелец)\n"
            "/digest_month [YYYY-MM] — сводка месяца (владелец)\n"
            "/status — статус бота (владелец)\n"
            "/cancel — отмена текущего действия"
        ),
        "private_bot": "Это приватный бот.",
        "shift_already_open": (
            "У тебя уже открыта смена с {start_time} на {site}. Сначала закрой её."
        ),
        "quick_start_no_history": (
            "Нет прошлой смены с объектом. Используй «Начать смену»."
        ),
        "quick_start_using_site": "Беру объект «{site}». Отправь геолокацию.",
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
        "cancelled": "❎ Действие отменено.",
        "no_shifts_today": "Сегодня смен не было.",
        "no_shifts_yesterday": "Вчера смен не было.",
        "yesterday_summary": "Вчера: {hours} ч. ({count} смен)",
        "yesterday_summary_amount": "Вчера: {hours} ч. ({count} смен), {amount} zł",
        "no_shifts_week": "На этой неделе смен не было.",
        "no_shifts_month": "В этом месяце смен не было.",
        "today_summary": "Сегодня: {hours} ч. ({count} смен)",
        "today_summary_amount": "Сегодня: {hours} ч. ({count} смен), {amount} zł",
        "week_summary": "Неделя: {hours} ч. ({count} смен)",
        "week_summary_amount": "Неделя: {hours} ч. ({count} смен), {amount} zł",
        "month_summary": "Месяц: {hours} ч. ({count} смен)",
        "month_summary_amount": "Месяц: {hours} ч. ({count} смен), {amount} zł",
        "me_usage": "Используй: /me YYYY-MM",
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
        "transfer_crew_usage": "Используй: /transfer_crew <tg_id> <crew_id>",
        "transfer_crew_done": "Работник {name} переведён в бригаду «{crew}».",
        "transfer_crew_error": "Не получилось перевести: {reason}.",
        "foremen_empty": "Бригадиров пока нет.",
        "foremen_list": "Бригадиры:\n{body}",
        "no_crew": "У тебя ещё нет бригады.",
        "invite_issued": (
            "Код приглашения: {code}\n"
            "Действует 72 часа. Перешли работнику — он напишет боту: /join {code}"
        ),
        "crew_empty": "В бригаде «{crew}» пока никого.",
        "crew_list": (
            "Бригада «{crew}» (участников: {count}, дефолтная ставка: {default_rate}):\n"
            "{body}"
        ),
        "remove_member_usage": "Используй: /remove_member <tg_id>",
        "remove_member_done": "Работник {name} выведён из бригады.",
        "remove_member_not_in_crew": "Работник не состоит в бригаде.",
        "remove_member_not_worker": "Удалять можно только работников.",
        "remove_member_open_shift": (
            "Сначала закрой текущую смену работника (/stop_for)."
        ),
        "join_usage": "Используй: /join <код>",
        "invite_error": "Не получилось присоединиться: {reason}.",
        "joined_crew": "Ты в бригаде «{crew}». Удачной смены!",
        "crew_no_shifts_today": "По бригаде сегодня смен нет.",
        "crew_no_shifts_week": "По бригаде на этой неделе смен нет.",
        "crew_no_shifts_month": "По бригаде в этом месяце смен нет.",
        "crew_today_summary": (
            "Бригада сегодня:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_today_summary_amount": (
            "Бригада сегодня:\n{body}\n\n"
            "Итого: {total_hours} ч ({total_count}), {total_amount} zł"
        ),
        "crew_week_summary": (
            "Бригада за неделю:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_week_summary_amount": (
            "Бригада за неделю:\n{body}\n\n"
            "Итого: {total_hours} ч ({total_count}), {total_amount} zł"
        ),
        "crew_month_summary": (
            "Бригада за месяц:\n{body}\n\nИтого: {total_hours} ч ({total_count})"
        ),
        "crew_month_summary_amount": (
            "Бригада за месяц:\n{body}\n\n"
            "Итого: {total_hours} ч ({total_count}), {total_amount} zł"
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
        "my_open_none": "Сейчас у тебя нет открытой смены.",
        "my_open_body": (
            "Открытая смена #{id}\n"
            "Объект: {site}\n"
            "Начало: {start}\n"
            "Прошло: {hours} ч"
        ),
        "leave_crew_owner": "Владелец не может покинуть бригаду.",
        "leave_crew_foreman": (
            "Бригадир не может выйти из своей бригады. "
            "Передай бригаду через владельца."
        ),
        "leave_crew_not_in": "Ты не состоишь в бригаде.",
        "leave_crew_open_shift": "Сначала закрой текущую смену.",
        "leave_crew_done": "Ты вышел из бригады.",
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
        "rate_set": "Ставка для {name} установлена: {rate} {currency}/ч.",
        "rate_changed_notify": "Твоя ставка обновлена: {rate} {currency}/ч.",
        "crew_rate_changed_notify": (
            "Ставка бригады по умолчанию обновлена: {rate} {currency}/ч. "
            "Если у тебя нет личной ставки — теперь будет применяться эта."
        ),
        "rate_not_set": "У тебя не задана ставка. Попроси бригадира — /set_rate.",
        "my_rate": "Твоя ставка: {rate} {currency}/ч.",
        "sites_empty": "Объектов пока нет. Создай первый при старте смены.",
        "sites_list": "Объекты:\n{body}",
        "site_not_found": "Объект не найден или не принадлежит тебе.",
        "set_site_rate_usage": "Используй: /set_site_rate <site_id> <ставка>",
        "site_rate_set": "Ставка для «{name}» установлена: {rate} zł/ч.",
        "unarchive_site_usage": "Используй: /unarchive_site <site_id>",
        "site_unarchived": "Объект «{name}» снова активен.",
        "rename_site_usage": "Используй: /rename_site <site_id> <новое название>",
        "site_renamed": "Объект «{old}» переименован в «{new}».",
        "site_info_usage": "Используй: /site_info <site_id>",
        "site_info_body": (
            "Объект #{id}\n"
            "Название: {name}\n"
            "Ставка: {rate}\n"
            "Архив: {archived}\n"
            "Граница: {polygon}\n"
            "Смен за 30 дней: {shifts_30d}"
        ),
        "sites_archive_empty": "Архивных объектов нет.",
        "sites_archive_list": "Архивные объекты:\n{body}",
        "admin_audit_usage": "Используй: /admin_audit [N] (по умолчанию 20)",
        "admin_audit_empty": "Журнал админ-действий пуст.",
        "admin_audit_list": "Журнал админ-действий:\n{body}",
        "archive_site_usage": "Используй: /archive_site <site_id>",
        "site_archived": "Объект «{name}» переведён в архив.",
        "crew_rates_list": "Ставки в бригаде «{crew}»:\n{body}",
        "break_started": "Перерыв начат в {time}. Когда вернёшься — /break_stop.",
        "break_status": "Перерыв с {start}, идёт уже {minutes} мин.",
        "break_auto_closed": (
            "Перерыв автоматически закрыт (превышен лимит). Длительность: {minutes} мин."
        ),
        "break_stopped": "Перерыв окончен. Длительность: {minutes} мин.",
        "already_on_break": "Перерыв уже идёт. Закрой его командой /break_stop.",
        "no_open_break": "Сейчас нет активного перерыва.",
        "add_break_usage": (
            "Используй: /add_break <shift_id> <YYYY-MM-DD HH:MM> <YYYY-MM-DD HH:MM>"
        ),
        "add_break_done": "Перерыв #{id} добавлен ({minutes} мин).",
        "edit_break_usage": (
            "Используй: /edit_break <break_id> start|end <YYYY-MM-DD HH:MM>"
        ),
        "edit_break_invalid_field": "Недопустимое поле. Доступные: {fields}.",
        "edit_break_done": "Перерыв #{id} обновлён ({field}).",
        "delete_break_usage": "Используй: /delete_break <break_id>",
        "delete_break_done": "Перерыв #{id} удалён.",
        "break_not_found": "Перерыв не найден.",
        "break_edit_invalid": "Не получилось обновить перерыв: {reason}.",
        "shifts_empty": "За последние 14 дней смен нет.",
        "shifts_list": "Последние смены:\n{body}",
        "edit_shift_usage": (
            "Используй: /edit_shift <id> <поле> <значение>\n"
            "Поля: start, end, note, work_type, site\n"
            "Дата/время: YYYY-MM-DD HH:MM (локальное время)"
        ),
        "edit_shift_invalid_field": "Недопустимое поле. Доступные: {fields}.",
        "edit_shift_invalid_value": "Не получилось обновить: {reason}.",
        "edit_shift_done": "Смена #{id} обновлена ({field}).",
        "delete_shift_usage": "Используй: /delete_shift <id>",
        "delete_shift_done": "Смена #{id} удалена.",
        "shift_not_found": "Смена не найдена.",
        "note_usage": "Используй: /note <текст заметки>",
        "note_saved": "Заметка сохранена.",
        "voice_disabled": "Голосовые заметки выключены (нет OPENAI_API_KEY).",
        "voice_no_open_shift": "Сначала открой смену, затем отправь голосовую.",
        "voice_failed": "Не удалось распознать голосовую. Попробуй ещё раз.",
        "voice_saved": "Заметка сохранена: {text}",
        "work_stats_usage": "Используй: /work_stats [YYYY-MM]",
        "site_stats_usage": "Используй: /site_stats [YYYY-MM]",
        "work_type_usage": "Используй: /work_type <тип работ>",
        "work_type_saved": "Тип работ: {value}.",
        "stop_for_usage": "Используй: /stop_for <tg_id>",
        "stop_for_done": "Смена пользователя {name} закрыта.",
        "no_open_shift_for_user": "У пользователя нет открытой смены.",
        "audit_usage": "Используй: /audit <shift_id>",
        "audit_empty": "По смене #{id} истории изменений нет.",
        "audit_list": "История смены #{id}:\n{body}",
        "set_crew_rate_usage": "Используй: /set_crew_rate <ставка>",
        "crew_rate_set": (
            "Ставка по умолчанию для бригады «{crew}»: {rate} {currency}/ч. "
            "Применяется к новым работникам без своей ставки."
        ),
        "shift_info_usage": "Используй: /shift_info <id>",
        "shift_info_body": (
            "Смена #{id}\n"
            "Работник: {user}\n"
            "Объект: {site}\n"
            "Начало: {start}\n"
            "Конец: {end}\n"
            "Часы (брутто/перерыв/нетто): {gross} / {break_h} / {net}\n"
            "Перерывов: {breaks_count}\n"
            "Заметка: {note}\n"
            "Тип работ: {work_type}\n"
            "Авто-закрытие: {auto}\n"
            "Фото: {photos}\n"
            "Записей в audit: {audit}"
        ),
        "shift_photos_usage": "Используй: /shift_photos <id>",
        "shift_photos_missing": "У этой смены нет сохранённых фото.",
        "photo_start_caption": "Фото начала смены",
        "photo_end_caption": "Фото окончания смены",
        "restore_shift_usage": "Используй: /restore_shift <audit_id>",
        "restore_shift_not_found": "Запись об удалении не найдена.",
        "restore_shift_already_exists": "Смена с этим id уже есть в базе.",
        "restore_shift_done": "Смена #{id} восстановлена.",
        "digest_month_usage": "Используй: /digest_month [YYYY-MM]",
        "geofence_set_usage": "Используй: /geofence_set <site_id>",
        "geofence_collecting": (
            "Редактирую границу объекта «{site}». "
            "Отправь геолокации точек по периметру (минимум 3). "
            "Когда закончишь — /geofence_save. Отмена — /geofence_cancel."
        ),
        "geofence_point_added": "Точка #{n} добавлена.",
        "geofence_too_few": "Нужно минимум 3 точки.",
        "geofence_saved": "Граница сохранена ({n} точек).",
        "geofence_cancelled": "Редактирование границы отменено.",
        "geofence_no_session": "Нет активного редактирования.",
        "geofence_clear_usage": "Используй: /geofence_clear <site_id>",
        "geofence_cleared": "Граница объекта «{name}» удалена.",
        "active_none": "Сейчас никто не на смене.",
        "active_summary": "Открытые смены:\n{body}",
        # Phase 5.1 — daily hours entry
        "h_prompt": "<b>🕒 Сколько часов отработал сегодня?</b>",
        "h_prompt_with_suggest": (
            "<b>🕒 Сколько часов отработал сегодня?</b>\n"
            "<i>Обычно у тебя {suggest} ч.</i>"
        ),
        "day_off_btn": "🌴 Выходной",
        "h_recorded_new": "✅ Записал <b>{hours} ч</b> за {date}.",
        "h_recorded_updated": (
            "✏️ Обновил {date}: было {old} ч, стало <b>{hours} ч</b>."
        ),
        "day_off_recorded_new": "🌴 Записал <b>выходной</b> за {date}.",
        "day_off_recorded_updated": (
            "✏️ Обновил {date}: было {old} ч, стало — <b>выходной</b>."
        ),
        "my_days_row_dayoff": "{date}: 🌴 выходной",
        "h_bad_value": (
            "⚠ Не понял число часов.\n"
            "Пример: /h 8 или /h 8.5 (от 0.25 до 24)."
        ),
        "h_edit_usage": (
            "💡 Используй: /edit_day YYYY-MM-DD <часы>\n"
            "Например: /edit_day 2026-05-10 8.5"
        ),
        "h_bad_date": "⚠ Неверная дата. Формат: YYYY-MM-DD.",
        "my_days_empty": (
            "<i>За последние 14 дней нет записей.</i>\n"
            "Используй /h &lt;часы&gt;, чтобы поставить часы за сегодня."
        ),
        "my_days_header": "<b>📋 Последние 14 дней</b>",
        "my_days_row": "{date}: <b>{hours} ч</b>",
        "my_days_total": "<b>Итого: {total} ч</b> за {n} дн.",
        # Phase 5.2 — advances + salary
        "advance_usage": (
            "Используй: /advance <tg_id> <сумма> [комментарий]. "
            "Например: /advance 123456789 500 Аванс на материалы"
        ),
        "advance_bad_amount": (
            "⚠ Сумма должна быть положительным числом.\n"
            "Пример: 500 или 500.50"
        ),
        "advance_recorded": (
            "<b>✅ Аванс зафиксирован.</b>\n"
            "Работник: <b>{name}</b>\n"
            "Сумма: <b>{amount} {currency}</b>\n"
            "Дата: {date}\n"
            "Комментарий: {note}"
        ),
        "advances_empty": "<i>Авансов за период нет.</i>",
        "advances_header": "<b>💵 Авансы за {year}-{month}</b>",
        "advance_row": "{date}: <b>{amount} {currency}</b> — {note}",
        "advances_total": "<b>Итого авансов: {total} {currency}</b>",
        "crew_advances_header": "<b>💵 Авансы бригады за {year}-{month}</b>",
        "crew_advances_member": "{name}: <b>{total} {currency}</b> ({n} шт)",
        "month_format": "⚠ Неверный формат месяца. Используй YYYY-MM, например 2026-05.",
        "salary_header": "<b>🧮 Расчёт за {year}-{month}</b>",
        "salary_hours": "Часы: <b>{h}</b>",
        "salary_earnings": "Начислено: <b>{earnings} {currency}</b>",
        "salary_advances": "Авансы: <b>{advances} {currency}</b>",
        "salary_net": "К выплате: <b>{net} {currency}</b>",
        "crew_salary_header": "<b>🧮 Зарплата бригады за {year}-{month}</b>",
        "crew_salary_row": (
            "{name}: <b>{hours} ч</b>, авансы {advances} {currency} "
            "→ к выплате <b>{net} {currency}</b>"
        ),
        "crew_salary_total": "<b>Итого к выплате: {total} {currency}</b>",
        "crew_salary_empty": "<i>За этот месяц нет ни часов, ни авансов.</i>",
        "user_not_found": "Пользователь не найден.",
        # Phase 5.3 — evening reminders
        "day_reminder_text": (
            "<b>⏰ Не забудь поставить часы за сегодня.</b>\n"
            "Сколько отработал?"
        ),
        "day_reminder_with_suggest": (
            "<b>⏰ Не забудь поставить часы за сегодня.</b>\n"
            "<i>Обычно у тебя {suggest} ч.</i>"
        ),
        "remind_on_usage": (
            "Используй: /remind_on HH (час по локальному времени, 0–23). "
            "Например: /remind_on 19"
        ),
        "remind_bad_hour": "⚠ Час должен быть числом от 0 до 23.",
        "remind_on_ok": (
            "✅ Вечернее напоминание включено: в <b>{hour}:00</b> "
            "по твоему часовому поясу."
        ),
        "remind_off_ok": "✅ Вечернее напоминание выключено.",
        # Phase 5.4 — feature toggles
        "settings_header": (
            "<b>⚙ Настройки бота</b>\n"
            "<i>Нажми, чтобы переключить:</i>"
        ),
        "settings_saved": "✅ Сохранено.",
        "settings_label_sites_enabled": "Объекты",
        "settings_label_crews_enabled": "Бригады",
        "settings_label_geofence_enabled": "Геозоны",
        "settings_label_legacy_clock_inout_enabled": "Старый режим (смены)",
        # Phase 6.3 — onboarding wizard
        "onb_welcome": (
            "Привет, {name}! Я бот для учёта рабочих часов.\n\n"
            "Давай быстро настроим — займёт минуту. Можно прервать /cancel."
        ),
        "onb_name_prompt": (
            "Как тебя записать в отчётах? "
            "Можно оставить «{tg_name}» — жми кнопку ниже — или прислать другое."
        ),
        "onb_name_use_tg_btn": "Оставить «{tg_name}»",
        "onb_name_bad": "⚠ Имя пустое. Пришли текстом или жми кнопку ниже.",
        "onb_name_saved": "✅ Имя: <b>{name}</b>",
        "onb_currency_prompt": (
            "В какой валюте считаем зарплату? "
            "Выбери ниже или пришли код из 3 букв (например: PLN, USD, EUR)."
        ),
        "onb_currency_bad": (
            "⚠ Код валюты — 3 латинские буквы (например, PLN).\n"
            "Попробуй ещё или жми кнопку."
        ),
        "onb_currency_saved": "✅ Валюта: <b>{currency}</b>.",
        "onb_rate_prompt": (
            "Какая у тебя ставка за час в {currency}? "
            "Например: 35 или 42.5\n"
            "Если не знаешь — жми «Пропустить», настроим позже через /set_rate."
        ),
        "onb_rate_skip_btn": "Пропустить",
        "onb_rate_bad": (
            "⚠ Не понял сумму. Пример: 35 или 42.5.\n"
            "Или жми «Пропустить»."
        ),
        "onb_rate_saved": "✅ Ставка: <b>{rate} {currency}/ч</b>",
        "onb_rate_skipped": "✅ Ставку пропустили.",
        "onb_reminder_prompt": (
            "Хочешь, я буду напоминать вечером поставить часы?"
        ),
        "onb_reminder_btn_19": "В 19:00",
        "onb_reminder_btn_20": "В 20:00",
        "onb_reminder_btn_no": "Не нужно",
        "onb_reminder_saved": "✅ Напомню в <b>{hour}:00</b>.",
        "onb_reminder_skipped": "✅ Без напоминаний — окей.",
        "onb_done": (
            "<b>🎉 Готово! Используй кнопки ниже:</b>\n"
            "\n"
            "<b>🕒 Часы за сегодня</b> — поставить часы\n"
            "<b>📆 Календарь</b> — редактировать любую дату\n"
            "<b>📊 Период</b> — расчёт за месяц\n"
            "<b>💸 Касса</b> — авансы и выплаты\n"
            "<b>📈 Отчёты</b> — сводка за N месяцев\n"
            "<b>⚙ Профиль</b> — имя, ставка, валюта, напоминание, часовой пояс\n"
            "\n"
            "Все команды — /help."
        ),
        "onb_cancelled": (
            "Настройка прервана. Запусти ещё раз через /start, когда будешь готов."
        ),
        # Phase 6.1 — simple-mode menu (Phase 6.8: reformatted)
        "menu_btn_hours": "🕒 Часы за сегодня",
        "menu_btn_calendar": "📆 Календарь",
        "menu_btn_period": "📊 Период",
        "menu_btn_cash": "💸 Касса",
        "menu_btn_reports": "📈 Отчёты",
        "menu_btn_profile": "⚙ Профиль",
        "menu_hint": "<b>Главное меню.</b> Жми кнопки или /help.",
        # Phase 6.6 — inline calendar
        "cal_header": "<b>📆 {month} {year}</b>\nЖми на дату, чтобы открыть.",
        "cal_legend": "• часы  🌴 выходной  💵 аванс  💰 выплата",
        "cal_btn_fill_workweek": "💼 Заполнить будни (10 ч)",
        "cal_fill_result": "✅ Добавлено будних дней: {n} × 10 ч.",
        "cal_fill_none": "ℹ Будни уже отмечены.",
        "cal_day_header": "<b>📅 {date}</b>",
        "cal_day_no_entry": "Часы: <i>не указаны</i>",
        "cal_day_off_line": "🌴 <b>Выходной</b>",
        "cal_day_hours": "Часы: <b>{hours}</b>",
        "cal_day_advances": "💵 Авансов: <b>{n}</b> на сумму <b>{total} {currency}</b>",
        "cal_day_advance_row": "  · <b>{amount} {currency}</b> за период {period}",
        "cal_day_payments": "💰 Выплат: <b>{n}</b> на сумму <b>{total} {currency}</b>",
        "cal_day_payment_row": "  · <b>{amount} {currency}</b> за период {period}",
        "cal_btn_set_hours": "🕒 Поставить часы",
        "cal_btn_dayoff": "🌴 Отметить выходной",
        "cal_btn_advance": "💵 Записать аванс",
        "cal_btn_payment": "💰 Записать выплату зарплаты",
        "cal_btn_back": "◀ К месяцу",
        "cal_btn_back_to_day": "◀ К дню",
        "cal_pick_hours": "Выбери часы за {date}:",
        "cal_advance_pick_period": (
            "💵 Аванс выдан {date}.\n"
            "За какой период? (аванс 5 мая может быть за апрель)"
        ),
        "cal_advance_prompt": (
            "Введи сумму аванса за {period} (выдано {date}, {currency}). "
            "Например: 200 или 350.50. /cancel — отмена."
        ),
        "cal_advance_recorded": (
            "✅ Аванс {amount} {currency} зачтён за {period} (выдан {date})."
        ),
        "cal_pay_pick_period": (
            "💰 Выплата зарплаты {date}.\n"
            "За какой период? (зарплата за апрель может быть выплачена в мае)"
        ),
        "cal_per_btn": "За {month} {year}",
        "cal_pay_amount_prompt": (
            "Введи сумму выплаты за {period} (выплачено {date}, {currency}). "
            "/cancel — отмена."
        ),
        "cal_pay_recorded": (
            "✅ Выплата {amount} {currency} зачтена за {period} (выплачено {date})."
        ),
        # Phase 6.11a — multi-month /report
        "report_header": "<b>📊 Отчёт за последние {months} мес.</b>",
        "report_row": (
            "<b>{period}</b>: {hours} ч · начислено <b>{earned} {currency}</b> · "
            "получено {received} {currency} · остаток <b>{remaining} {currency}</b> {tag}"
        ),
        "report_row_unpriced": "<b>{period}</b>: {hours} ч · (без ставки)",
        "report_tag_settled": "✅",
        "report_tag_pending": "⏳",
        "report_tag_partial": "🟡",
        "report_tag_overpaid": "🟢+",
        "report_tag_unpriced": "❔",
        "report_totals": (
            "<b>Итого</b>: <b>{hours} ч</b> · начислено <b>{earned} {currency}</b> · "
            "получено {received} {currency} · долг <b>{owed} {currency}</b>"
        ),
        "report_total_overpaid": "Переплата (всего): <b>{overpaid} {currency}</b>",
        "report_bad_arg": "⚠ Использование: /report [N] — где N от 1 до 24 месяцев.",
        "report_btn_xlsx": "📥 XLSX",
        "report_btn_pdf": "📄 PDF",
        "report_btn_png": "📈 PNG",
        "report_menu_prompt": "📈 За какой период?",
        "report_menu_1m": "1 мес",
        "report_menu_3m": "3 мес",
        "report_menu_6m": "6 мес",
        "report_menu_12m": "12 мес",
        "report_menu_24m": "24 мес",
        "period_btn_png": "📈 График",
        "period_btn_forecast": "🔮 Прогноз",
        # Phase 7.1 — full XLSX backup
        "backup_caption": (
            "📦 Резервная копия\n"
            "Дней: {days}  ·  Авансов: {advances}  ·  Выплат: {payments}"
        ),
        # Phase 7.8 — /export-archive
        "archive_caption": "📦 Архив отчёта за {months} мес. (XLSX + PDF + PNG)",
        # Phase 7.1b — /restore
        "restore_prompt": (
            "Пришли .xlsx, выгруженный командой /backup. "
            "Существующие записи не будут изменены — добавятся только новые.\n"
            "/cancel — отмена."
        ),
        "restore_need_document": (
            "Жду файл .xlsx от /backup. /cancel — отмена."
        ),
        "restore_bad_format": (
            "⚠ Это не .xlsx. Пришли резервную копию от команды /backup."
        ),
        "restore_too_large": (
            "⚠ Файл слишком большой (лимит 5 МБ). Это точно бэкап от /backup?"
        ),
        "restore_failed": "⚠ Не получилось прочитать файл: {error}",
        "restore_preview": (
            "<b>📋 Файл прочитан.</b>\n"
            "<i>Существующее не трогаем — только добавим:</i>\n"
            "• Дней: <b>{days}</b>\n"
            "• Авансов: <b>{advances}</b>\n"
            "• Выплат: <b>{payments}</b>\n"
            "\n"
            "Применить?"
        ),
        "restore_btn_confirm": "✅ Применить",
        "restore_btn_cancel": "❌ Отменить",
        "restore_cancelled": "❎ Восстановление отменено.",
        "restore_done": (
            "<b>✅ Восстановление завершено.</b>\n"
            "Дни: добавлено <b>{days_in}</b>, пропущено {days_skip}\n"
            "Авансы: добавлено <b>{adv_in}</b>, пропущено {adv_skip}\n"
            "Выплаты: добавлено <b>{pay_in}</b>, пропущено {pay_skip}"
        ),
        "share_backup_issued": (
            "🔑 Одноразовый код для переноса данных:\n"
            "{token}\n"
            "Действует до {expires}.\n"
            "На новом аккаунте: /restore_from <код>."
        ),
        "share_backup_failed": (
            "Не получилось выдать код: {reason}. "
            "Если активных слишком много — подожди, пока истекут, "
            "или попроси владельца поднять лимит."
        ),
        "restore_from_usage": (
            "Используй: /restore_from <код>\n"
            "Код выдаёт /share_backup на старом аккаунте."
        ),
        "restore_from_failed": (
            "⚠ Не получилось применить код: {reason}."
        ),
        "restore_from_preview": (
            "<b>📋 Код принят.</b>\n"
            "<i>Существующее не трогаем — только добавим:</i>\n"
            "• Дней: <b>{days}</b>\n"
            "• Авансов: <b>{advances}</b>\n"
            "• Выплат: <b>{payments}</b>\n"
            "\n"
            "Применить?"
        ),
        "restore_from_cloud_preview": (
            "<b>📋 Бэкап скачан из облака.</b>\n"
            "<i>Существующее не трогаем — только добавим:</i>\n"
            "• Дней: <b>{days}</b>\n"
            "• Авансов: <b>{advances}</b>\n"
            "• Выплат: <b>{payments}</b>\n"
            "\n"
            "Применить?"
        ),
        "cloud_backup_disabled": (
            "Облачное хранилище не настроено — обратись к владельцу."
        ),
        "cloud_backup_uploaded": (
            "☁ Бэкап загружен в облако.\n"
            "Ключ: {key}\n"
            "Размер: {size_kb} КБ\n"
            "Действует до {expires}.\n"
            "Восстановить: /restore_from_cloud <ключ>."
        ),
        "cloud_backup_failed": (
            "Не получилось загрузить в облако: {reason}."
        ),
        "restore_from_cloud_usage": (
            "Используй: /restore_from_cloud <ключ>\n"
            "Ключ выдаёт /backup_to_cloud."
        ),
        "restore_from_cloud_failed": (
            "Не получилось вытащить бэкап из облака: {reason}."
        ),
        # Phase 7.2 — smart reminders
        "gap_nudge_with_last": (
            "<b>👋 Давно не виделись.</b>\n"
            "Последняя запись часов: <b>{last_day}</b>.\n"
            "Уже <b>{gap}</b> рабочих дня(-ей) без отметок — добавишь сейчас?"
        ),
        "gap_nudge_no_entries": (
            "<b>👋 Я не вижу у тебя пока ни одной записи часов.</b>\n"
            "Поставь часы за сегодня командой /h 8 или открой /calendar."
        ),
        "debt_ping_header": (
            "<b>💼 Старые незакрытые периоды</b> <i>(более 30 дней)</i>:"
        ),
        "debt_ping_row": (
            "• <b>{period}</b> — остаток <b>{remaining} {currency}</b>"
        ),
        "debt_ping_footer": (
            "<b>Итого: {total} {currency}.</b> Подробнее: /owed"
        ),
        # Phase 6.7 — period / cashflow / owed accounting
        "period_pick_prompt": "<b>📊 За какой месяц показать?</b>",
        "period_older_btn": "◀ Раньше",
        "period_header": "<b>📊 Период {month} {year}</b>",
        "period_hours_rate": "Часы: <b>{hours}</b>  ·  Ставка: {rate}",
        "period_no_rate": "Часы: <b>{hours}</b>  ·  Ставка: не задана",
        "period_earnings": "Начислено: <b>{earnings} {currency}</b>",
        "period_earnings_unpriced": "Начислено: — (нет ставки)",
        "period_advances_header": "💵 <b>Авансы</b> (внутри периода): <b>{total} {currency}</b>",
        "period_advance_row": "  · {date}: <b>{amount} {currency}</b> — {note}",
        "period_payments_header": "💰 <b>Выплаты за этот период</b>: <b>{total} {currency}</b>",
        "period_payment_row": "  · {date}: <b>{amount} {currency}</b> — {note}",
        "period_payment_row_late": (
            "  · {date}: <b>{amount} {currency}</b> ← выплачено в {paid_month} {paid_year}"
        ),
        "period_no_advances": "💵 Авансов нет.",
        "period_no_payments": "💰 Выплат нет.",
        "period_received": "Получено: <b>{received} {currency}</b>",
        "period_remaining": "Осталось: <b>{remaining} {currency}</b>",
        "period_status_pending": "Статус: 🔴 <b>не выплачено</b>",
        "period_status_partial": "Статус: 🟡 <b>частично</b>",
        "period_status_settled": "Статус: 🟢 <b>рассчитано</b>",
        "period_status_overpaid": "Статус: 🔵 <b>переплата {overpaid} {currency}</b>",
        "period_status_unpriced": "Статус: ⚪ нет ставки",
        "cash_header": "<b>💸 Денежный поток {month} {year}</b>\nВсего: <b>{total} {currency}</b>",
        "cash_empty": "В этом месяце выплат и авансов не было.",
        "cash_row_advance": "{date} 💵 аванс <b>{amount} {currency}</b> (за {period}) — {note}",
        "cash_row_payment": "{date} 💰 выплата <b>{amount} {currency}</b> (за {period}) — {note}",
        "owed_header": "<b>📋 Незакрытые периоды:</b>",
        "owed_empty": "Все периоды рассчитаны 🟢",
        "owed_row_pending": (
            "🔴 <b>{period}</b>: ничего не получено, "
            "должно <b>{remaining} {currency}</b>"
        ),
        "owed_row_partial": (
            "🟡 <b>{period}</b>: получено {received} из {earnings}, "
            "осталось <b>{remaining} {currency}</b>"
        ),
        "owed_total": "<b>Итого долг: {total} {currency}</b>",
        # Phase 7.4 — /forecast
        "forecast_header": "<b>🔮 Прогноз на {month} {year}</b>",
        "forecast_mtd": (
            "Сейчас: <b>{hours} ч</b>, <b>{earnings} {currency}</b>."
        ),
        "forecast_business_days": (
            "Будни: {elapsed} из {total} (осталось {remaining})\n{bar}"
        ),
        "forecast_no_projection": (
            "Пока нет данных за этот месяц — прогноз появится после "
            "первого рабочего дня."
        ),
        "forecast_projection": (
            "Если темп сохранится: <b>{hours} ч</b>, ~<b>{earnings} {currency}</b> "
            "к концу месяца."
        ),
        "forecast_remaining_hours": "Осталось добрать ~<b>{hours} ч</b>.",
        # Phase 7.x — /range
        "range_usage": (
            "💡 Используй: /range YYYY-MM-DD YYYY-MM-DD\n"
            "Пример: /range 2026-05-01 2026-05-15"
        ),
        "range_bad_format": (
            "⚠ Не понял даты. Формат: /range YYYY-MM-DD YYYY-MM-DD."
        ),
        "range_header": "<b>🧮 Период {start} … {end}</b>",
        "range_hours": "Часы: <b>{hours} ч</b> за {days} дн.",
        "range_earnings": "Заработано: <b>{earnings} {currency}</b>.",
        "range_no_rate": (
            "Ставка не задана — рассчитать заработок не могу. "
            "Установи в /profile."
        ),
        "range_picker_prompt": (
            "<b>🧮 Выбери период</b>\n"
            "или пришли: /range YYYY-MM-DD YYYY-MM-DD"
        ),
        "range_btn_this_week": "📅 Эта неделя",
        "range_btn_last_week": "📅 Прошлая неделя",
        "range_btn_this_month": "📅 Этот месяц",
        "range_btn_last_month": "📅 Прошлый месяц",
        "range_btn_7d": "📅 7 дней",
        "range_btn_30d": "📅 30 дней",
        # Phase 6.9 — /profile editor
        "profile_header": (
            "<b>⚙ Профиль</b>\n"
            "Имя: <b>{name}</b>\n"
            "Ставка: <b>{rate}</b>\n"
            "Валюта: <b>{currency}</b>\n"
            "Напоминание: <b>{reminder}</b>\n"
            "Часовой пояс: <b>{timezone}</b>"
        ),
        "profile_rate_none": "не задана",
        "profile_reminder_none": "выключено",
        "profile_reminder_at": "{hour}:00",
        "profile_btn_name": "✏ Имя",
        "profile_btn_rate": "💰 Ставка",
        "profile_btn_currency": "💱 Валюта",
        "profile_btn_reminder": "⏰ Напоминание",
        "profile_btn_timezone": "🌐 Часовой пояс",
        "profile_btn_close": "Закрыть",
        "profile_name_prompt": "Пришли новое имя. /cancel — отмена.",
        "profile_name_bad": "⚠ Имя пустое. Пришли текстом или /cancel.",
        "profile_name_saved": "✅ Имя обновлено: <b>{name}</b>.",
        "profile_rate_prompt": (
            "Пришли новую ставку за час в {currency}. Например: 35 или 42.5\n"
            "Чтобы убрать ставку — пришли «-». /cancel — отмена."
        ),
        "profile_rate_bad": "⚠ Не понял сумму. Пример: 35 или 42.5, или «-».",
        "profile_rate_saved": "✅ Ставка обновлена: <b>{rate} {currency}/ч</b>.",
        "profile_rate_cleared": "✅ Ставка убрана.",
        "profile_currency_prompt": (
            "Пришли код валюты (3 буквы), например: PLN, USD, EUR, RUB, BYN, UAH.\n"
            "/cancel — отмена."
        ),
        "profile_currency_bad": (
            "⚠ Код валюты — 3 латинские буквы (например, PLN). Попробуй ещё."
        ),
        "profile_currency_saved": "✅ Валюта обновлена: <b>{currency}</b>.",
        "profile_reminder_prompt": (
            "Когда напоминать поставить часы?"
        ),
        "profile_reminder_btn_off": "Не нужно",
        "profile_reminder_saved": "✅ Напоминание: <b>{value}</b>.",
        "profile_timezone_default": "по умолчанию",
        "profile_timezone_prompt": (
            "Выбери часовой пояс из списка или пришли IANA-имя "
            "(например: Europe/Warsaw). /cancel — отмена."
        ),
        "profile_timezone_btn_default": "Использовать по умолчанию",
        "profile_timezone_bad": (
            "⚠ Неизвестный часовой пояс. Пример: Europe/Warsaw."
        ),
        "profile_timezone_saved": "✅ Часовой пояс: <b>{tz}</b>.",
        "profile_timezone_cleared": "✅ Часовой пояс сброшен на значение по умолчанию.",
        "profile_closed": "Закрыто.",
        # Phase 5.5 — cutover
        "feature_disabled": (
            "Эта функция выключена. Владелец может включить её в /settings."
        ),
        "help_core": (
            "<b>🕒 Запись часов</b>\n"
            "/h &lt;часы&gt; — часы за сегодня (например: /h 8)\n"
            "/calendar — календарь: редактировать любую дату\n"
            "/my_days — мои последние 14 дней\n"
            "\n"
            "<b>📊 Отчёты и аналитика</b>\n"
            "/period [YYYY-MM] — расчёт за период\n"
            "/cash [YYYY-MM] — денежный поток за месяц\n"
            "/owed — что ещё не выплачено\n"
            "/forecast — прогноз до конца месяца\n"
            "/report [N] — отчёт за N месяцев (XLSX/PDF/PNG)\n"
            "/range — сумма за произвольный период\n"
            "/export_archive [N] — все три формата в ZIP\n"
            "\n"
            "<b>💾 Бэкап и перенос</b>\n"
            "/backup — резервная копия (XLSX, все данные)\n"
            "/restore — загрузить .xlsx-бэкап\n"
            "/share_backup — одноразовый код переноса\n"
            "/restore_from &lt;код&gt; — принять данные по коду\n"
            "/backup_to_cloud — сохранить в облако\n"
            "/restore_from_cloud &lt;ключ&gt; — восстановить из облака\n"
            "\n"
            "<b>⚙ Профиль и настройки</b>\n"
            "/profile — имя, ставка, валюта, напоминание, часовой пояс\n"
            "/remind_on HH — включить вечернее напоминание\n"
            "/remind_off — выключить напоминание\n"
            "/settings — настройки режима\n"
            "/cancel — отмена текущего действия\n"
            "\n"
            "<i>Можно писать словами: «отчёт за 6 мес», «период май», "
            "«касса за апрель», «долг».</i>"
        ),
        "help_section_legacy": (
            "\n\n<b>⏱ Смены (старый режим)</b>\n"
            "/today /me_yesterday /week /month /me YYYY-MM\n"
            "/quick_start /my_open /shifts /shift_info &lt;id&gt;\n"
            "/break_start /break_stop /break_status\n"
            "/note &lt;текст&gt; /work_type &lt;тип&gt;\n"
            "/export YYYY-MM — выгрузка в Excel"
        ),
        "help_section_sites": (
            "\n\n<b>🏗 Объекты</b>\n"
            "/sites /site_info &lt;id&gt; /sites_archive\n"
            "/set_site_rate &lt;id&gt; &lt;ставка&gt;\n"
            "/archive_site &lt;id&gt; /unarchive_site &lt;id&gt; "
            "/rename_site &lt;id&gt; &lt;название&gt;"
        ),
        "help_section_geofence": (
            "\n\n<b>📍 Геозоны</b>\n"
            "/geofence_set &lt;id&gt; /geofence_save /geofence_cancel "
            "/geofence_clear &lt;id&gt;"
        ),
        "help_section_crews": (
            "\n\n<b>👥 Бригады</b>\n"
            "/join &lt;код&gt; /invite /crew /leave_crew\n"
            "/crew_today /crew_week /crew_month /crew_export YYYY-MM\n"
            "/crew_advances [YYYY-MM] /crew_salary [YYYY-MM]\n"
            "/add_foreman &lt;tg_id&gt; (владелец) "
            "/transfer_crew &lt;tg_id&gt; &lt;crew_id&gt; (владелец)"
        ),
    },
}


def t(key: str, /, locale: str = "ru", **kwargs: object) -> str:
    template = STRINGS.get(locale, STRINGS["ru"]).get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
