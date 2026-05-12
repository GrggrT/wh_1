"""Phase 7.1: ``/backup`` — full XLSX export of the user's accounting data.

Exports profile + day_entries + advances + salary_payments into a single
workbook. Useful as a personal safety net before product changes or
account deletion.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message
from sqlalchemy import select

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import Advance, DayEntry, SalaryPayment, User
from src.services.reports.backup import backup_filename, build_backup_xlsx

router = Router()


@router.message(Command("backup"))
async def cmd_backup(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    tz = ZoneInfo(get_settings().timezone)
    today = datetime.now(tz=tz).date()
    async for session in get_session():
        days = (
            await session.execute(
                select(DayEntry)
                .where(DayEntry.user_id == db_user.id)
                .order_by(DayEntry.day),
            )
        ).scalars().all()
        advs = (
            await session.execute(
                select(Advance)
                .where(Advance.user_id == db_user.id)
                .order_by(Advance.day),
            )
        ).scalars().all()
        pays = (
            await session.execute(
                select(SalaryPayment)
                .where(SalaryPayment.user_id == db_user.id)
                .order_by(SalaryPayment.paid_on),
            )
        ).scalars().all()

    buf = build_backup_xlsx(
        db_user, list(days), list(advs), list(pays), today=today,
    )
    document = BufferedInputFile(
        buf.getvalue(), filename=backup_filename(db_user, today),
    )
    await message.answer_document(
        document,
        caption=t(
            "backup_caption",
            days=len(days),
            advances=len(advs),
            payments=len(pays),
        ),
    )
