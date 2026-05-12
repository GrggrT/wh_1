"""All user-facing strings. Russian only in Phase 0, structured for future i18n."""

from typing import Final

STRINGS: Final[dict[str, dict[str, str]]] = {
    "ru": {
        "welcome": "Привет, {name}! Я бот для учёта рабочего времени на стройке.",
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
        "cancelled": "Действие отменено.",
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
        "h_prompt": "Сколько часов отработал сегодня?",
        "h_prompt_with_suggest": (
            "Сколько часов отработал сегодня? Обычно у тебя {suggest} ч."
        ),
        "day_off_btn": "🌴 Выходной",
        "h_recorded_new": "✅ Записал {hours} ч за {date}.",
        "h_recorded_updated": "✏️ Обновил {date}: было {old} ч, стало {hours} ч.",
        "day_off_recorded_new": "🌴 Записал выходной за {date}.",
        "day_off_recorded_updated": (
            "✏️ Обновил {date}: было {old} ч, стало — выходной."
        ),
        "my_days_row_dayoff": "{date}: выходной",
        "h_bad_value": (
            "Не понял число часов. Пример: /h 8 или /h 8.5. "
            "Допустимо от 0.25 до 24."
        ),
        "h_edit_usage": (
            "Используй: /edit_day YYYY-MM-DD <часы>. "
            "Например: /edit_day 2026-05-10 8.5"
        ),
        "h_bad_date": "Неверная дата. Используй формат YYYY-MM-DD.",
        "my_days_empty": (
            "За последние 14 дней нет записей. "
            "Используй /h <часы>, чтобы поставить часы за сегодня."
        ),
        "my_days_header": "Последние 14 дней:",
        "my_days_row": "{date}: {hours} ч",
        "my_days_total": "Итого: {total} ч за {n} дн.",
        # Phase 5.2 — advances + salary
        "advance_usage": (
            "Используй: /advance <tg_id> <сумма> [комментарий]. "
            "Например: /advance 123456789 500 Аванс на материалы"
        ),
        "advance_bad_amount": (
            "Сумма должна быть положительным числом. Пример: 500 или 500.50"
        ),
        "advance_recorded": (
            "✅ Аванс зафиксирован.\n"
            "Работник: {name}\n"
            "Сумма: {amount} {currency}\n"
            "Дата: {date}\n"
            "Комментарий: {note}"
        ),
        "advances_empty": "Авансов за период нет.",
        "advances_header": "Авансы за {year}-{month}:",
        "advance_row": "{date}: {amount} {currency} — {note}",
        "advances_total": "Итого авансов: {total} {currency}",
        "crew_advances_header": "Авансы бригады за {year}-{month}:",
        "crew_advances_member": "{name}: {total} {currency} ({n} шт)",
        "month_format": "Неверный формат месяца. Используй YYYY-MM, например 2026-05.",
        "salary_header": "Расчёт за {year}-{month}:",
        "salary_hours": "Часы: {h}",
        "salary_earnings": "Начислено: {earnings} {currency}",
        "salary_advances": "Авансы: {advances} {currency}",
        "salary_net": "К выплате: {net} {currency}",
        "crew_salary_header": "Зарплата бригады за {year}-{month}:",
        "crew_salary_row": (
            "{name}: {hours} ч, авансы {advances} {currency} → к выплате {net} {currency}"
        ),
        "crew_salary_total": "Итого к выплате: {total} {currency}",
        "crew_salary_empty": "За этот месяц нет ни часов, ни авансов.",
        "user_not_found": "Пользователь не найден.",
        # Phase 5.3 — evening reminders
        "day_reminder_text": (
            "Не забудь поставить часы за сегодня. Сколько отработал?"
        ),
        "day_reminder_with_suggest": (
            "Не забудь поставить часы за сегодня. Обычно у тебя {suggest} ч."
        ),
        "remind_on_usage": (
            "Используй: /remind_on HH (час по локальному времени, 0–23). "
            "Например: /remind_on 19"
        ),
        "remind_bad_hour": "Час должен быть числом от 0 до 23.",
        "remind_on_ok": (
            "Вечернее напоминание включено: в {hour}:00 (часовой пояс сервера)."
        ),
        "remind_off_ok": "Вечернее напоминание выключено.",
        # Phase 5.4 — feature toggles
        "settings_header": (
            "Настройки бота. Нажми, чтобы переключить:"
        ),
        "settings_saved": "Сохранено.",
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
        "onb_name_bad": "Имя пустое. Пришли текстом или жми кнопку ниже.",
        "onb_name_saved": "Имя: {name}",
        "onb_rate_prompt": (
            "Какая у тебя ставка за час в {currency}? "
            "Например: 35 или 42.5\n"
            "Если не знаешь — жми «Пропустить», настроим позже через /set_rate."
        ),
        "onb_rate_skip_btn": "Пропустить",
        "onb_rate_bad": (
            "Не понял сумму. Пример: 35 или 42.5. Или жми «Пропустить»."
        ),
        "onb_rate_saved": "Ставка: {rate} {currency}/ч",
        "onb_rate_skipped": "Ставку пропустили.",
        "onb_reminder_prompt": (
            "Хочешь, я буду напоминать вечером поставить часы?"
        ),
        "onb_reminder_btn_19": "В 19:00",
        "onb_reminder_btn_20": "В 20:00",
        "onb_reminder_btn_no": "Не нужно",
        "onb_reminder_saved": "Напомню в {hour}:00.",
        "onb_reminder_skipped": "Без напоминаний — окей.",
        "onb_done": (
            "Готово! Используй кнопки ниже:\n"
            "🕒 Часы за сегодня — поставить часы\n"
            "📅 Мои дни — последние 14 дней\n"
            "💰 Зарплата — расчёт за месяц\n"
            "💵 Авансы — мои авансы\n\n"
            "Всё через /help."
        ),
        "onb_cancelled": (
            "Настройка прервана. Запусти ещё раз через /start, когда будешь готов."
        ),
        # Phase 6.1 — simple-mode menu (Phase 6.8: reformatted)
        "menu_btn_hours": "🕒 Часы за сегодня",
        "menu_btn_calendar": "📆 Календарь",
        "menu_btn_period": "📊 Период",
        "menu_btn_cash": "💸 Касса",
        "menu_btn_my_days": "📅 Мои дни",
        "menu_hint": "Главное меню. Жми кнопки или /help.",
        # Phase 6.6 — inline calendar
        "cal_header": "📆 {month} {year}\nЖми на дату, чтобы открыть.",
        "cal_legend": "• часы  🌴 выходной  💵 аванс  💰 выплата",
        "cal_day_header": "📅 {date}",
        "cal_day_no_entry": "Часы: не указаны",
        "cal_day_off_line": "🌴 Выходной",
        "cal_day_hours": "Часы: {hours}",
        "cal_day_advances": "💵 Авансов: {n} на сумму {total} {currency}",
        "cal_day_payments": "💰 Выплат: {n} на сумму {total} {currency}",
        "cal_day_payment_row": "  · {amount} {currency} за период {period}",
        "cal_btn_set_hours": "🕒 Поставить часы",
        "cal_btn_dayoff": "🌴 Отметить выходной",
        "cal_btn_advance": "💵 Записать аванс",
        "cal_btn_payment": "💰 Записать выплату зарплаты",
        "cal_btn_back": "◀ К месяцу",
        "cal_btn_back_to_day": "◀ К дню",
        "cal_pick_hours": "Выбери часы за {date}:",
        "cal_advance_prompt": (
            "Введи сумму аванса за {date} ({currency}). "
            "Например: 200 или 350.50. /cancel — отмена."
        ),
        "cal_advance_recorded": "✅ Аванс {amount} {currency} за {date} записан.",
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
        # Phase 6.7 — period / cashflow / owed accounting
        "period_header": "📊 Период {month} {year}",
        "period_hours_rate": "Часы: {hours}  ·  Ставка: {rate}",
        "period_no_rate": "Часы: {hours}  ·  Ставка: не задана",
        "period_earnings": "Начислено: {earnings} {currency}",
        "period_earnings_unpriced": "Начислено: — (нет ставки)",
        "period_advances_header": "💵 Авансы (внутри периода): {total} {currency}",
        "period_advance_row": "  · {date}: {amount} {currency} — {note}",
        "period_payments_header": "💰 Выплаты за этот период: {total} {currency}",
        "period_payment_row": "  · {date}: {amount} {currency} — {note}",
        "period_payment_row_late": (
            "  · {date}: {amount} {currency} ← выплачено в {paid_month} {paid_year}"
        ),
        "period_no_advances": "💵 Авансов нет.",
        "period_no_payments": "💰 Выплат нет.",
        "period_received": "Получено: {received} {currency}",
        "period_remaining": "Осталось: {remaining} {currency}",
        "period_status_pending": "Статус: 🔴 не выплачено",
        "period_status_partial": "Статус: 🟡 частично",
        "period_status_settled": "Статус: 🟢 рассчитано",
        "period_status_overpaid": "Статус: 🔵 переплата {overpaid} {currency}",
        "period_status_unpriced": "Статус: ⚪ нет ставки",
        "cash_header": "💸 Денежный поток {month} {year}: всего {total} {currency}",
        "cash_empty": "В этом месяце выплат и авансов не было.",
        "cash_row_advance": "{date} 💵 аванс {amount} {currency} (за {period}) — {note}",
        "cash_row_payment": "{date} 💰 выплата {amount} {currency} (за {period}) — {note}",
        "owed_header": "📋 Незакрытые периоды:",
        "owed_empty": "Все периоды рассчитаны 🟢",
        "owed_row_pending": "🔴 {period}: ничего не получено, должно {remaining} {currency}",
        "owed_row_partial": (
            "🟡 {period}: получено {received} из {earnings}, "
            "осталось {remaining} {currency}"
        ),
        "owed_total": "Итого долг: {total} {currency}",
        # Phase 6.9 — /profile editor
        "profile_header": (
            "⚙ Профиль\n"
            "Имя: {name}\n"
            "Ставка: {rate}\n"
            "Валюта: {currency}\n"
            "Напоминание: {reminder}"
        ),
        "profile_rate_none": "не задана",
        "profile_reminder_none": "выключено",
        "profile_reminder_at": "{hour}:00",
        "profile_btn_name": "✏ Имя",
        "profile_btn_rate": "💰 Ставка",
        "profile_btn_currency": "💱 Валюта",
        "profile_btn_reminder": "⏰ Напоминание",
        "profile_btn_close": "Закрыть",
        "profile_name_prompt": "Пришли новое имя. /cancel — отмена.",
        "profile_name_bad": "Имя пустое. Пришли текстом или /cancel.",
        "profile_name_saved": "Имя обновлено: {name}.",
        "profile_rate_prompt": (
            "Пришли новую ставку за час в {currency}. Например: 35 или 42.5\n"
            "Чтобы убрать ставку — пришли «-». /cancel — отмена."
        ),
        "profile_rate_bad": "Не понял сумму. Пример: 35 или 42.5, или «-».",
        "profile_rate_saved": "Ставка обновлена: {rate} {currency}/ч.",
        "profile_rate_cleared": "Ставка убрана.",
        "profile_currency_prompt": (
            "Пришли код валюты (3 буквы), например: PLN, USD, EUR, RUB, BYN, UAH.\n"
            "/cancel — отмена."
        ),
        "profile_currency_bad": (
            "Код валюты должен быть из 3 латинских букв (например, PLN). Попробуй ещё."
        ),
        "profile_currency_saved": "Валюта обновлена: {currency}.",
        "profile_reminder_prompt": (
            "Когда напоминать поставить часы?"
        ),
        "profile_reminder_btn_off": "Не нужно",
        "profile_reminder_saved": "Напоминание: {value}.",
        "profile_closed": "Закрыто.",
        # Phase 5.5 — cutover
        "feature_disabled": (
            "Эта функция выключена. Владелец может включить её в /settings."
        ),
        "help_core": (
            "Команды:\n"
            "/h <часы> — поставить часы за сегодня (например: /h 8)\n"
            "/calendar — календарь: редактировать любую дату\n"
            "/period [YYYY-MM] — расчёт за период (часы + выплаты)\n"
            "/cash [YYYY-MM] — денежный поток за месяц\n"
            "/owed — что ещё не выплачено\n"
            "/my_days — мои последние 14 дней\n"
            "/profile — имя, ставка, валюта, напоминание\n"
            "/my_rate — моя ставка\n"
            "/remind_on HH — вечернее напоминание\n"
            "/remind_off — отключить напоминание\n"
            "/whoami — кто я\n"
            "/settings — настройки режима\n"
            "/cancel — отмена текущего действия"
        ),
        "help_section_legacy": (
            "\n\nСмены (старый режим):\n"
            "/today /me_yesterday /week /month /me YYYY-MM\n"
            "/quick_start /my_open /shifts /shift_info <id>\n"
            "/break_start /break_stop /break_status\n"
            "/note <текст> /work_type <тип>\n"
            "/export YYYY-MM — выгрузка в Excel"
        ),
        "help_section_sites": (
            "\n\nОбъекты:\n"
            "/sites /site_info <id> /sites_archive\n"
            "/set_site_rate <id> <ставка>\n"
            "/archive_site <id> /unarchive_site <id> /rename_site <id> <название>"
        ),
        "help_section_geofence": (
            "\n\nГеозоны:\n"
            "/geofence_set <id> /geofence_save /geofence_cancel /geofence_clear <id>"
        ),
        "help_section_crews": (
            "\n\nБригады:\n"
            "/join <код> /invite /crew /leave_crew\n"
            "/crew_today /crew_week /crew_month /crew_export YYYY-MM\n"
            "/crew_advances [YYYY-MM] /crew_salary [YYYY-MM]\n"
            "/add_foreman <tg_id> (владелец) /transfer_crew <tg_id> <crew_id> (владелец)"
        ),
    },
}


def t(key: str, locale: str = "ru", **kwargs: object) -> str:
    template = STRINGS.get(locale, STRINGS["ru"]).get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template
