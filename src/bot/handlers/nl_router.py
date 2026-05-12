"""Phase 6.11e: catch-all natural-language dispatcher.

Registered LAST in ``main.py`` so slash commands, reply-keyboard text
buttons, inline callbacks, and FSM state-bound handlers all get the
first shot at the message. Only leftover plain text reaches this router.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters.command import CommandObject
from aiogram.types import Message

from src.bot.handlers.accounting import (
    cmd_cash,
    cmd_forecast,
    cmd_owed,
    cmd_period,
)
from src.bot.handlers.report import cmd_report
from src.core.config import get_settings
from src.core.models import User
from src.services.reports.parser import NLIntent, parse_intent

router = Router()


def _ym_arg(intent: NLIntent) -> str | None:
    if intent.year is None or intent.month is None:
        return None
    return f"{intent.year:04d}-{intent.month:02d}"


@router.message(F.text)
async def nl_dispatch(
    message: Message, db_user: User | None = None,
) -> None:
    if db_user is None or not message.text:
        return
    text = message.text
    if text.startswith("/"):
        return  # slash commands handled elsewhere

    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    intent = parse_intent(text, today=today)
    if intent is None:
        return

    if intent.kind == "owed":
        await cmd_owed(message, db_user=db_user)
        return
    if intent.kind == "forecast":
        await cmd_forecast(message, db_user=db_user)
        return
    if intent.kind == "cash":
        await cmd_cash(
            message,
            CommandObject(prefix="/", command="cash", args=_ym_arg(intent)),
            db_user=db_user,
        )
        return
    if intent.kind == "period":
        await cmd_period(
            message,
            CommandObject(prefix="/", command="period", args=_ym_arg(intent)),
            db_user=db_user,
        )
        return
    if intent.kind == "report":
        months_arg = (
            str(intent.months) if intent.months is not None else None
        )
        await cmd_report(
            message,
            CommandObject(prefix="/", command="report", args=months_arg),
            db_user=db_user,
        )
