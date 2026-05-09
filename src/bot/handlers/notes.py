"""Mid-shift annotations: /note and /work_type."""

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.crews import ROLE_FOREMAN, ROLE_OWNER, get_crew_for_foreman
from src.services.shift_edits import get_shift
from src.services.shifts import get_open_shift, stop_shift

router = Router()


@router.message(Command("note"))
async def cmd_note(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("note_usage"))
        return
    note_text = command.args.strip()
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        shift.note = note_text
        await session.commit()
    await message.answer(t("note_saved"))


@router.message(Command("work_type"))
async def cmd_work_type(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("work_type_usage"))
        return
    work_type = command.args.strip()
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        shift.work_type = work_type
        await session.commit()
    await message.answer(t("work_type_saved", value=work_type))


@router.message(Command("stop_for"))
async def cmd_stop_for(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Foreman/owner: close a forgotten open shift for a crew member."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("stop_for_usage"))
        return
    try:
        target_tg_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("stop_for_usage"))
        return
    target_name = ""
    async for session in get_session():
        target = (
            await session.execute(select(User).where(User.tg_id == target_tg_id))
        ).scalar_one_or_none()
        if target is None:
            await message.answer(t("user_not_seen"))
            return
        if db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None or target.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        open_shift = await get_open_shift(session, target.id)
        if open_shift is None:
            await message.answer(t("no_open_shift_for_user"))
            return
        await stop_shift(session, open_shift)
        target_name = target.name
        await session.commit()
    await message.answer(t("stop_for_done", name=target_name))


@router.message(Command("audit"))
async def cmd_audit(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Foreman/owner: view audit log entries for a shift."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("audit_usage"))
        return
    try:
        shift_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("audit_usage"))
        return
    from src.core.models import AuditLog

    lines: list[str] = []
    async for session in get_session():
        # Authorization: foreman must scope to crew member shift
        shift = await get_shift(session, shift_id)
        if shift is not None and db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            if crew is None:
                await message.answer(t("not_authorized"))
                return
            owner = (
                await session.execute(
                    select(User).where(User.id == shift.user_id),
                )
            ).scalar_one_or_none()
            if owner is None or owner.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == "shift",
                AuditLog.entity_id == shift_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(20)
        )
        entries = list((await session.execute(stmt)).scalars().all())
        for entry in entries:
            ts = entry.created_at.strftime("%Y-%m-%d %H:%M")
            lines.append(f"• {ts} — {entry.action}: {entry.diff}")
    if not lines:
        await message.answer(t("audit_empty", id=shift_id))
        return
    await message.answer(t("audit_list", id=shift_id, body="\n".join(lines)))
