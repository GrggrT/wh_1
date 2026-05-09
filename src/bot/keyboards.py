from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.bot.strings import t
from src.core.models import Site


def main_menu(role: str = "worker") -> ReplyKeyboardMarkup:
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
