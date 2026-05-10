"""Shift listing, edit, delete, and restore with audit log."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message
from sqlalchemy import func, select

from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import AuditLog, Shift, Site, User
from src.services.breaks import get_breaks_for_shift, total_break_hours
from src.services.crews import ROLE_FOREMAN, ROLE_OWNER, get_crew_for_foreman
from src.services.reports import compute_hours
from src.services.shift_edits import (
    EDITABLE_FIELDS,
    ShiftEditError,
    delete_shift,
    format_shift_summary,
    get_shift,
    list_recent_crew_shifts,
    list_recent_shifts,
    update_shift_field,
)

router = Router()


def _can_admin_shift(actor: User, shift_user_id: int, foreman_crew_id: int | None) -> bool:
    """Owner: any shift. Foreman: shifts of users in their crew."""
    if actor.role == ROLE_OWNER:
        return True
    if actor.role != ROLE_FOREMAN:
        return False
    return foreman_crew_id is not None  # exact crew membership checked by caller


@router.message(Command("shifts"))
async def cmd_shifts(message: Message, db_user: User | None = None) -> None:
    if db_user is None:
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    lines: list[str] = []
    async for session in get_session():
        shifts = await list_recent_shifts(session, db_user.id)
        if not shifts:
            await message.answer(t("shifts_empty"))
            return
        site_ids = {s.site_id for s in shifts if s.site_id}
        sites_map: dict[int, str] = {}
        if site_ids:
            res = await session.execute(select(Site).where(Site.id.in_(site_ids)))
            sites_map = {s.id: s.name for s in res.scalars().all()}
        for s in shifts:
            site_name = sites_map.get(s.site_id) if s.site_id else None
            lines.append(format_shift_summary(s, site_name, tz))
    await message.answer(t("shifts_list", body="\n".join(lines)))


@router.message(Command("crew_shifts"))
async def cmd_crew_shifts(message: Message, db_user: User | None = None) -> None:
    """Foreman: last 14d of crew shifts (up to 30) with user names + IDs.

    Owner: redirected to use /active or per-user /shifts; not implemented globally.
    """
    if db_user is None or db_user.role != ROLE_FOREMAN:
        await message.answer(t("not_authorized"))
        return
    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    lines: list[str] = []
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        shifts = await list_recent_crew_shifts(session, crew.id)
        if not shifts:
            await message.answer(t("shifts_empty"))
            return
        user_ids = {s.user_id for s in shifts}
        site_ids = {s.site_id for s in shifts if s.site_id}
        users_map: dict[int, str] = {}
        if user_ids:
            res = await session.execute(select(User).where(User.id.in_(user_ids)))
            users_map = {u.id: u.name for u in res.scalars().all()}
        sites_map: dict[int, str] = {}
        if site_ids:
            res = await session.execute(select(Site).where(Site.id.in_(site_ids)))
            sites_map = {s.id: s.name for s in res.scalars().all()}
        for s in shifts:
            site_name = sites_map.get(s.site_id) if s.site_id else None
            who = users_map.get(s.user_id, "—")
            lines.append(f"{who}: {format_shift_summary(s, site_name, tz)}")
    await message.answer(t("shifts_list", body="\n".join(lines)))


@router.message(Command("edit_shift"))
async def cmd_edit_shift(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("edit_shift_usage"))
        return
    parts = command.args.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer(t("edit_shift_usage"))
        return
    try:
        shift_id = int(parts[0])
    except ValueError:
        await message.answer(t("edit_shift_usage"))
        return
    field = parts[1].lower()
    if field not in EDITABLE_FIELDS:
        await message.answer(
            t("edit_shift_invalid_field", fields=", ".join(EDITABLE_FIELDS)),
        )
        return
    value = parts[2]

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    async for session in get_session():
        shift = await get_shift(session, shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        if db_user.role == ROLE_FOREMAN:
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
        try:
            await update_shift_field(session, db_user, shift, field, value, tz)
        except ShiftEditError as exc:
            await message.answer(t("edit_shift_invalid_value", reason=str(exc)))
            return
        await session.commit()
    await message.answer(t("edit_shift_done", id=shift_id, field=field))


@router.message(Command("delete_shift"))
async def cmd_delete_shift(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("delete_shift_usage"))
        return
    try:
        shift_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("delete_shift_usage"))
        return

    async for session in get_session():
        shift = await get_shift(session, shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        if db_user.role == ROLE_FOREMAN:
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
        await delete_shift(session, db_user, shift)
        await session.commit()
    await message.answer(t("delete_shift_done", id=shift_id))


@router.message(Command("shift_photos"))
async def cmd_shift_photos(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Resend the start/end photos of a shift via Telegram file_id."""
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("shift_photos_usage"))
        return
    try:
        shift_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("shift_photos_usage"))
        return

    start_id: str | None = None
    end_id: str | None = None
    async for session in get_session():
        shift = await get_shift(session, shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        # Authorization: owner of shift, owner role, or foreman of crew member
        if db_user.role == ROLE_OWNER or shift.user_id == db_user.id:
            pass
        elif db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            owner = (
                await session.execute(
                    select(User).where(User.id == shift.user_id),
                )
            ).scalar_one_or_none()
            if crew is None or owner is None or owner.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        else:
            await message.answer(t("not_authorized"))
            return
        start_id = shift.start_photo_file_id
        end_id = shift.end_photo_file_id

    sent_any = False
    if start_id:
        await message.answer_photo(start_id, caption=t("photo_start_caption"))
        sent_any = True
    if end_id:
        await message.answer_photo(end_id, caption=t("photo_end_caption"))
        sent_any = True
    if not sent_any:
        await message.answer(t("shift_photos_missing"))


@router.message(Command("shift_info"))
async def cmd_shift_info(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Detail view for one shift. Worker sees own; foreman sees crew; owner all."""
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("shift_info_usage"))
        return
    try:
        shift_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("shift_info_usage"))
        return

    settings = get_settings()
    tz = ZoneInfo(settings.timezone)
    body = ""
    async for session in get_session():
        shift = await get_shift(session, shift_id)
        if shift is None:
            await message.answer(t("shift_not_found"))
            return
        # Authorization
        if db_user.role == ROLE_OWNER or shift.user_id == db_user.id:
            pass
        elif db_user.role == ROLE_FOREMAN:
            crew = await get_crew_for_foreman(session, db_user.id)
            owner = (
                await session.execute(
                    select(User).where(User.id == shift.user_id),
                )
            ).scalar_one_or_none()
            if crew is None or owner is None or owner.crew_id != crew.id:
                await message.answer(t("not_authorized"))
                return
        else:
            await message.answer(t("not_authorized"))
            return

        owner_user = (
            await session.execute(select(User).where(User.id == shift.user_id))
        ).scalar_one()
        site_name = "—"
        if shift.site_id is not None:
            site_obj = (
                await session.execute(select(Site).where(Site.id == shift.site_id))
            ).scalar_one_or_none()
            if site_obj is not None:
                site_name = site_obj.name
        breaks = await get_breaks_for_shift(session, shift.id)
        audit_count = (
            await session.execute(
                select(func.count(AuditLog.id)).where(
                    AuditLog.entity_type == "shift",
                    AuditLog.entity_id == shift.id,
                ),
            )
        ).scalar_one()

        start_local = shift.start_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
        if shift.end_at is None:
            end_local = "—"
            gross = Decimal(0)
        else:
            end_local = shift.end_at.astimezone(tz).strftime("%Y-%m-%d %H:%M")
            gross = compute_hours(shift.start_at, shift.end_at)
        break_h = (
            total_break_hours(breaks, shift.start_at, shift.end_at)
            if shift.end_at is not None and breaks
            else Decimal(0)
        )
        net = gross - break_h
        if net < 0:
            net = Decimal(0)

        photos_flag = []
        if shift.start_photo_file_id:
            photos_flag.append("старт")
        if shift.end_photo_file_id:
            photos_flag.append("конец")
        photos_str = ", ".join(photos_flag) if photos_flag else "нет"

        body = t(
            "shift_info_body",
            id=str(shift.id),
            user=f"{owner_user.name} (tg_id={owner_user.tg_id})",
            site=site_name,
            start=start_local,
            end=end_local,
            gross=str(gross.quantize(Decimal("0.01"))),
            break_h=str(break_h.quantize(Decimal("0.01"))),
            net=str(net.quantize(Decimal("0.01"))),
            note=shift.note or "—",
            work_type=shift.work_type or "—",
            auto="да" if shift.auto_closed else "нет",
            audit=str(audit_count),
            photos=photos_str,
            breaks_count=str(len(breaks)),
        )
    await message.answer(body)


@router.message(Command("restore_shift"))
async def cmd_restore_shift(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    """Owner: restore a deleted shift from its audit_log snapshot."""
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("restore_shift_usage"))
        return
    try:
        audit_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("restore_shift_usage"))
        return

    async for session in get_session():
        entry = (
            await session.execute(select(AuditLog).where(AuditLog.id == audit_id))
        ).scalar_one_or_none()
        if entry is None or entry.action != "delete" or entry.entity_type != "shift":
            await message.answer(t("restore_shift_not_found"))
            return
        snapshot_obj = entry.diff.get("snapshot")
        if not isinstance(snapshot_obj, dict):
            await message.answer(t("restore_shift_not_found"))
            return
        snapshot: dict[str, object] = snapshot_obj

        def _as_int(val: object) -> int | None:
            if isinstance(val, int):
                return val
            if isinstance(val, str) and val.isdigit():
                return int(val)
            return None

        def _as_str(val: object) -> str | None:
            return val if isinstance(val, str) else None

        def _as_dt(val: object) -> datetime | None:
            return datetime.fromisoformat(val) if isinstance(val, str) else None

        shift_id_int = _as_int(snapshot.get("id"))
        user_id_int = _as_int(snapshot.get("user_id"))
        start_dt = _as_dt(snapshot.get("start_at"))
        if shift_id_int is None or user_id_int is None or start_dt is None:
            await message.answer(t("restore_shift_not_found"))
            return

        existing = await get_shift(session, shift_id_int)
        if existing is not None:
            await message.answer(t("restore_shift_already_exists"))
            return

        new_shift = Shift(
            id=shift_id_int,
            user_id=user_id_int,
            site_id=_as_int(snapshot.get("site_id")),
            start_at=start_dt,
            end_at=_as_dt(snapshot.get("end_at")),
            note=_as_str(snapshot.get("note")),
            work_type=_as_str(snapshot.get("work_type")),
        )
        session.add(new_shift)
        session.add(
            AuditLog(
                user_id=db_user.id,
                entity_type="shift",
                entity_id=new_shift.id,
                action="restore",
                diff={"from_audit_id": audit_id, "snapshot": snapshot},
            ),
        )
        await session.commit()
    await message.answer(t("restore_shift_done", id=shift_id_int))


__all__ = ["router", "_can_admin_shift"]
