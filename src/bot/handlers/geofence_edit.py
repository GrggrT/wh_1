"""Geofence editor: owner/foreman draw a site polygon by sending location messages."""

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.states import GeofenceEdit
from src.bot.strings import t
from src.core.db import get_session
from src.core.models import Site, User
from src.services.audit import write_audit
from src.services.crews import ROLE_FOREMAN, ROLE_OWNER, get_crew_for_foreman
from src.services.geofence import (
    build_polygon_wkt,
    clear_site_polygon,
    set_site_polygon,
)

router = Router()


async def _resolve_site_owner_id(
    session: AsyncSession, db_user: User,
) -> int | None:
    if db_user.role == ROLE_OWNER:
        return db_user.id
    if db_user.role == ROLE_FOREMAN:
        crew = await get_crew_for_foreman(session, db_user.id)
        return crew.foreman_user_id if crew is not None else None
    return None


@router.message(Command("geofence_set"))
async def cmd_geofence_set(
    message: Message,
    command: CommandObject,
    state: FSMContext,
    db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("geofence_set_usage"))
        return
    try:
        site_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("geofence_set_usage"))
        return
    site_name = ""
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        site = (
            await session.execute(select(Site).where(Site.id == site_id))
        ).scalar_one_or_none()
        if site is None or site.user_id != owner_id:
            await message.answer(t("site_not_found"))
            return
        site_name = site.name
    await state.set_state(GeofenceEdit.collecting_points)
    await state.update_data(site_id=site_id, points=[])
    await message.answer(t("geofence_collecting", site=site_name))


@router.message(GeofenceEdit.collecting_points, F.location)
async def on_location_point(message: Message, state: FSMContext) -> None:
    if message.location is None:
        return
    data = await state.get_data()
    points: list[tuple[float, float]] = list(data.get("points", []))
    points.append((message.location.longitude, message.location.latitude))
    await state.update_data(points=points)
    await message.answer(t("geofence_point_added", n=str(len(points))))


@router.message(GeofenceEdit.collecting_points, Command("geofence_save"))
async def cmd_geofence_save(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    data = await state.get_data()
    site_id = data.get("site_id")
    points: list[tuple[float, float]] = list(data.get("points", []))
    if not isinstance(site_id, int):
        await state.clear()
        await message.answer(t("geofence_no_session"))
        return
    if len(points) < 3:
        await message.answer(t("geofence_too_few"))
        return
    try:
        build_polygon_wkt(points)
    except ValueError:
        await message.answer(t("geofence_too_few"))
        return
    async for session in get_session():
        await set_site_polygon(session, site_id, points)
        if db_user is not None:
            await write_audit(
                session, db_user.id, "site", site_id, "geofence_set",
                {"points_count": len(points)},
            )
        await session.commit()
    await state.clear()
    await message.answer(t("geofence_saved", n=str(len(points))))


@router.message(GeofenceEdit.collecting_points, Command("geofence_cancel"))
async def cmd_geofence_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(t("geofence_cancelled"))


@router.message(Command("geofence_clear"))
async def cmd_geofence_clear(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role not in (ROLE_OWNER, ROLE_FOREMAN):
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("geofence_clear_usage"))
        return
    try:
        site_id = int(command.args.strip())
    except ValueError:
        await message.answer(t("geofence_clear_usage"))
        return
    site_name = ""
    async for session in get_session():
        owner_id = await _resolve_site_owner_id(session, db_user)
        if owner_id is None:
            await message.answer(t("no_crew"))
            return
        site = (
            await session.execute(select(Site).where(Site.id == site_id))
        ).scalar_one_or_none()
        if site is None or site.user_id != owner_id:
            await message.answer(t("site_not_found"))
            return
        site_name = site.name
        await clear_site_polygon(session, site_id)
        await write_audit(
            session, db_user.id, "site", site_id, "geofence_clear", {},
        )
        await session.commit()
    await message.answer(t("geofence_cleared", name=site_name))


__all__ = ["router"]
