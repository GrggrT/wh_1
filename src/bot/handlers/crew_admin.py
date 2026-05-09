"""Owner and foreman commands: manage foremen, crews, and invite codes."""

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from src.bot.strings import t
from src.core.db import get_session
from src.core.models import User
from src.services.crews import (
    ROLE_FOREMAN,
    ROLE_OWNER,
    CrewError,
    InviteError,
    get_crew_for_foreman,
    issue_invite_code,
    list_crew_members,
    list_foremen,
    promote_to_foreman,
    redeem_invite_code,
)

router = Router()


# --- OWNER ---


@router.message(Command("add_foreman"))
async def cmd_add_foreman(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    if not command.args:
        await message.answer(t("add_foreman_usage"))
        return
    parts = command.args.split(maxsplit=1)
    try:
        target_tg_id = int(parts[0])
    except ValueError:
        await message.answer(t("add_foreman_usage"))
        return
    crew_name = parts[1].strip() if len(parts) > 1 else f"Бригада {target_tg_id}"
    async for session in get_session():
        try:
            crew = await promote_to_foreman(session, target_tg_id, crew_name)
        except CrewError:
            await message.answer(t("user_not_seen"))
            return
        await session.commit()
    await message.answer(t("foreman_added", crew=crew.name))


@router.message(Command("foremen"))
async def cmd_list_foremen(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role != ROLE_OWNER:
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        foremen = await list_foremen(session)
    if not foremen:
        await message.answer(t("foremen_empty"))
        return
    lines = [f"• {f.name} (tg_id={f.tg_id})" for f in foremen]
    await message.answer(t("foremen_list", body="\n".join(lines)))


# --- FOREMAN ---


@router.message(Command("invite"))
async def cmd_invite(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        invite = await issue_invite_code(session, crew.id, db_user.id)
        await session.commit()
        code = invite.code
    await message.answer(t("invite_issued", code=code))


@router.message(Command("crew"))
async def cmd_crew(message: Message, db_user: User | None = None) -> None:
    if db_user is None or db_user.role not in (ROLE_FOREMAN, ROLE_OWNER):
        await message.answer(t("not_authorized"))
        return
    crew_name: str | None = None
    members: list[User] = []
    async for session in get_session():
        crew = await get_crew_for_foreman(session, db_user.id)
        if crew is None:
            await message.answer(t("no_crew"))
            return
        crew_name = crew.name
        members = await list_crew_members(session, crew.id)
    assert crew_name is not None
    if not members:
        await message.answer(t("crew_empty", crew=crew_name))
        return
    lines = [f"• {m.name}" for m in members]
    await message.answer(t("crew_list", crew=crew_name, body="\n".join(lines)))


# --- WORKER ---


@router.message(Command("join"))
async def cmd_join(
    message: Message, command: CommandObject, db_user: User | None = None,
) -> None:
    if db_user is None:
        return
    if not command.args:
        await message.answer(t("join_usage"))
        return
    code = command.args.strip().upper()
    async for session in get_session():
        # Reload user inside this session so changes persist correctly.
        from sqlalchemy import select

        from src.core.models import User as UserModel

        fresh = (
            await session.execute(
                select(UserModel).where(UserModel.id == db_user.id),
            )
        ).scalar_one()
        try:
            crew = await redeem_invite_code(session, code, fresh)
        except InviteError as exc:
            await message.answer(t("invite_error", reason=str(exc)))
            return
        await session.commit()
    await message.answer(t("joined_crew", crew=crew.name))
