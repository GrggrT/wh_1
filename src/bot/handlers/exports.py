"""Export handler: /export YYYY-MM."""

import re
from datetime import date
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.exporters.xlsx import export_xlsx
from src.services.reports import get_shifts_for_period
from src.services.shifts import ensure_user, get_user_sites

router = Router()

PERIOD_RE = re.compile(r"^(\d{4})-(\d{2})$")


@router.message(Command("export"))
async def cmd_export(message: Message) -> None:
    assert message.from_user is not None
    assert message.text is not None

    parts = message.text.strip().split()
    if len(parts) < 2 or not PERIOD_RE.match(parts[1]):
        await message.answer("Usage: /export YYYY-MM")
        return

    match = PERIOD_RE.match(parts[1])
    assert match is not None
    year, month = int(match.group(1)), int(match.group(2))

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)

    from datetime import timedelta

    start_date = date(year, month, 1)
    next_month = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    end_date = next_month - timedelta(days=1)

    async for session in get_session():
        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        shifts = await get_shifts_for_period(session, user.id, start_date, end_date, tz)

        if not shifts:
            await message.answer(t("export_empty", period=parts[1]))
            return

        sites_list = await get_user_sites(session, user.id)
        # Also include archived sites referenced by shifts
        from sqlalchemy import select

        from src.core.models import Site

        site_ids = {s.site_id for s in shifts if s.site_id}
        if site_ids:
            res = await session.execute(select(Site).where(Site.id.in_(site_ids)))
            all_sites = list(res.scalars().all())
        else:
            all_sites = sites_list

        sites_dict = {s.id: s for s in all_sites}

        buffer = export_xlsx(shifts, sites_dict, user, tz, parts[1])

    filename = f"timesheet_{message.from_user.full_name}_{parts[1]}.xlsx"
    doc = BufferedInputFile(buffer.read(), filename=filename)
    await message.answer_document(doc, caption=t("export_ready", period=parts[1]))
