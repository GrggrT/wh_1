from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.bot.strings import t
from src.core.models import Site
from src.services.app_settings import SettingsSnapshot


def main_menu(role: str = "worker") -> ReplyKeyboardMarkup:
    """Legacy clock-in/out menu. Used inside the shift FSM where the user has
    already opted into the legacy flow. For the default app menu use
    :func:`simple_menu` (settings-aware)."""
    rows: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text=f"\U0001f7e2 {t('start_shift_btn')}"),
            KeyboardButton(text=f"\U0001f534 {t('stop_shift_btn')}"),
        ],
    ]
    if role in ("foreman", "owner"):
        rows.append(
            [
                KeyboardButton(text=f"\U0001f465 {t('crew_today_btn')}"),
                KeyboardButton(text=f"\U0001f4e9 {t('invite_btn')}"),
            ],
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def simple_menu(
    snap: SettingsSnapshot, role: str = "worker",
) -> ReplyKeyboardMarkup:
    """Default reply keyboard for the single-user accounting product.

    Layout (Phase 6.11a):
      [🕒 Часы за сегодня] [📆 Календарь]
      [📊 Период]          [💸 Касса]
      [📊 Отчёты]          [⚙ Профиль]
    Plus optional crews row when the matching toggle is on.
    """
    rows: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text=t("menu_btn_hours")),
            KeyboardButton(text=t("menu_btn_calendar")),
        ],
        [
            KeyboardButton(text=t("menu_btn_period")),
            KeyboardButton(text=t("menu_btn_cash")),
        ],
        [
            KeyboardButton(text=t("menu_btn_reports")),
            KeyboardButton(text=t("menu_btn_profile")),
        ],
    ]
    if role in ("foreman", "owner") and snap.crews_enabled:
        rows.append(
            [
                KeyboardButton(text=f"\U0001f465 {t('crew_today_btn')}"),
                KeyboardButton(text=f"\U0001f4e9 {t('invite_btn')}"),
            ],
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def site_selection(sites: list[Site]) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for site in sites:
        buttons.append([InlineKeyboardButton(text=site.name, callback_data=f"site:{site.id}")])
    buttons.append([InlineKeyboardButton(text=f"\u2795 {t('new_site')}", callback_data="site:new")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_stop() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=f"\u2705 {t('confirm')}", callback_data="stop:confirm"),
                InlineKeyboardButton(text=f"\u274c {t('cancel_btn')}", callback_data="stop:cancel"),
            ],
        ]
    )


def location_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"\U0001f4cd {t('send_location')}", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_photo() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("skip"))]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
