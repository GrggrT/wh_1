"""Lunch / pause break handlers."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.audit import write_audit
from src.services.breaks import (
    BREAK_EDITABLE_FIELDS,
    BreakEditError,
    BreakError,
    create_manual_break,
    delete_break_row,
    get_break,
    get_open_break,
    start_break,
    stop_break,
    update_break_time,
)
from src.services.crews import ROLE_FOREMAN, ROLE_OWNER, get_crew_for_foreman
from src.services.shift_edits import get_shift, parse_local_datetime
from src.services.shifts import get_open_shift

router = Router()


@router.message(Command("break_start"))
async def cmd_break_start(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    start_time = ""
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        try:
            new_break = await start_break(session, shift)
        except BreakError as exc:
            if str(exc) == "already_on_break":
                await message.answer(t("already_on_break"))
            else:
                await message.answer(t("no_open_shift"))
            return
        start_time = new_break.start_at.strftime("%H:%M")
        await session.commit()
    await message.answer(t("break_started", time=start_time))


@router.message(Command("break_status"))
async def cmd_break_status(message: Message, db_user: User | None = None) -> None:
    """Report whether the user is on a break and how long it has run."""
    if db_user is None:
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        open_break = await get_open_break(session, shift.id)
        if open_break is None:
            await message.answer(t("no_open_break"))
            return
        elapsed_min = int(
            (datetime.now(tz=UTC) - open_break.start_at).total_seconds() // 60,
        )
        local_start = open_break.start_at.astimezone(tz).strftime("%H:%M")
    await message.answer(
        t("break_status", start=local_start, minutes=elapsed_min),
    )


@router.message(Command("break_stop"))
async def cmd_break_stop(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    minutes = 0
    async for session in get_session():
        shift = await get_open_shift(session, db_user.id)
        if shift is None:
            await message.answer(t("no_open_shift"))
            return
        try:
            closed = await stop_break(session, shift.id)
        except BreakError:
            await message.answer(t("no_open_break"))
            return
        assert closed.end_at is not None
        minutes = int((closed.end_at - closed.start_at).total_seconds() // 60)
        await session.commit()
    await message.answer(t("break_stopped", minutes=minutes))


async def _foreman_can_admin_shift_user(
    session: AsyncSession, foreman: User, shift_user_id: int,
) -> bool:
    """Check the foreman owns the crew the shift's worker belongs to."""
    crew = await get_crew_for_foreman(session, foreman.id)
    if crew is None:
        return False
    owner = (
        await session.execute(select(User).where(User.id == shift_user_id))
    ).scalar_one_or_none()
    return owner is not None and owner.crew_id == crew.id


@router.message(Command("add_break"))
async def cmd_add_break(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner/foreman: add a manual break to an existing shift.

    Usage: /add_break <shift_id> <YYYY-MM-DD HH:MM> <YYYY-MM-DD HH:MM>
    """
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("add_break_usage"))
        return
    # Expect: <shift_id> "YYYY-MM-DD HH:MM" "YYYY-MM-DD HH:MM"
    parts = command.args.split()
    if len(parts) != 5:
        await message.answer(t("add_break_usage"))
        return
    try:
        shift_id = int(parts[0])
    except ValueError:
        await message.answer(t("add_break_usage"))
        return
    raw_start = f"{parts[1]} {parts[2]}"
    raw_end = f"{parts[3]} {parts[4]}"

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    try:
        start_at = parse_local_datetime(raw_start, tz)
        end_at = parse_local_datetime(raw_end, tz)
    except ValueError:
        await message.answer(t("add_break_usage"))
        return

    new_id = 0
    async for session in get_session():
        shift = await get_shift(session, shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        if db_user.role == ROLE_FOREMAN and not await _foreman_can_admin_shift_user(
            session, db_user, shift.user_id,
        ):
            await message.answer(t("not_authorized"))
            return
        try:
            new_break = await create_manual_break(session, shift, start_at, end_at)
        except BreakEditError as exc:
            await message.answer(t("break_edit_invalid", reason=str(exc)))
            return
        await write_audit(
            session,
            actor_id=db_user.id,
            entity_type="break",
            entity_id=new_break.id,
            action="create",
            diff={
                "shift_id": shift.id,
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
            },
        )
        new_id = new_break.id
        await session.commit()
    minutes = int((end_at - start_at).total_seconds() // 60)
    await message.answer(t("add_break_done", id=new_id, minutes=minutes))


@router.message(Command("edit_break"))
async def cmd_edit_break(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner/foreman: edit a break's start or end time.

    Usage: /edit_break <break_id> start|end <YYYY-MM-DD HH:MM>
    """
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("edit_break_usage"))
        return
    parts = command.args.split()
    if len(parts) != 4:
        await message.answer(t("edit_break_usage"))
        return
    try:
        break_id = int(parts[0])
    except ValueError:
        await message.answer(t("edit_break_usage"))
        return
    field = parts[1].lower()
    if field not in BREAK_EDITABLE_FIELDS:
        await message.answer(
            t("edit_break_invalid_field", fields=", ".join(BREAK_EDITABLE_FIELDS)),
        )
        return
    raw_dt = f"{parts[2]} {parts[3]}"
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    try:
        new_dt = parse_local_datetime(raw_dt, tz)
    except ValueError:
        await message.answer(t("edit_break_usage"))
        return

    async for session in get_session():
        br = await get_break(session, break_id)
        if br is None:
            await message.answer(t("break_not_found"))
            return
        shift = await get_shift(session, br.shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        if db_user.role == ROLE_FOREMAN and not await _foreman_can_admin_shift_user(
            session, db_user, shift.user_id,
        ):
            await message.answer(t("not_authorized"))
            return
        try:
            diff = await update_break_time(session, br, shift, field, new_dt)
        except BreakEditError as exc:
            await message.answer(t("break_edit_invalid", reason=str(exc)))
            return
        await write_audit(
            session,
            actor_id=db_user.id,
            entity_type="break",
            entity_id=br.id,
            action="edit",
            diff=diff,
        )
        await session.commit()
    await message.answer(t("edit_break_done", id=break_id, field=field))


@router.message(Command("delete_break"))
async def cmd_delete_break(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner/foreman: delete a break."""
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("delete_break_usage"))
        return
    try:
        break_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("delete_break_usage"))
        return

    async for session in get_session():
        br = await get_break(session, break_id)
        if br is None:
            await message.answer(t("break_not_found"))
            return
        shift = await get_shift(session, br.shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        if db_user.role == ROLE_FOREMAN and not await _foreman_can_admin_shift_user(
            session, db_user, shift.user_id,
        ):
            await message.answer(t("not_authorized"))
            return
        diff = await delete_break_row(session, br)
        await write_audit(
            session,
            actor_id=db_user.id,
            entity_type="break",
            entity_id=break_id,
            action="delete",
            diff=diff,
        )
        await session.commit()
    await message.answer(t("delete_break_done", id=break_id))
