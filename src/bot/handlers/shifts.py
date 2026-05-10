"""Shift start/stop handlers with FSM."""

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select

from src.bot.keyboards import (
    confirm_stop,
    location_request,
    main_menu,
    site_selection,
    skip_photo,
)
from src.bot.states import ShiftStart, ShiftStop
from src.bot.strings import t
from src.core.config import get_settings
from src.core.db import get_session
from src.core.models import User
from src.services.breaks import get_breaks_for_shift, total_break_hours
from src.services.geofence import check_point_in_site
from src.services.photos import archive_shift_photo
from src.services.reports import compute_hours
from src.services.shifts import (
    ShiftAlreadyOpenError,
    create_site,
    get_last_site_id,
    get_open_shift,
    get_visible_sites_for_user,
    resolve_effective_site_owner_id,
    start_shift,
    stop_shift,
)

router = Router()


# --- START SHIFT ---


@router.message(Command("quick_start"))
async def cmd_quick_start(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    """Skip site selection: reuse the user's last-used site, jump straight to location."""
    assert message.from_user is not None
    site_name: str | None = None
    async for session in get_session():
        from src.services.shifts import ensure_user

        user = await ensure_user(
            session, message.from_user.id, message.from_user.full_name,
        )
        open_shift = await get_open_shift(session, user.id)
        if open_shift is not None:
            start_time = open_shift.start_at.strftime("%H:%M")
            existing_site = "—"
            if open_shift.site_id:
                from src.core.models import Site

                site_obj = (
                    await session.execute(
                        select(Site).where(Site.id == open_shift.site_id),
                    )
                ).scalar_one_or_none()
                if site_obj:
                    existing_site = site_obj.name
            await message.answer(
                t(
                    "shift_already_open",
                    start_time=start_time,
                    site=existing_site,
                ),
                reply_markup=main_menu(),
            )
            return
        last_site_id = await get_last_site_id(session, user.id)
        if last_site_id is None:
            await message.answer(t("quick_start_no_history"))
            return
        from src.core.models import Site

        site_obj = (
            await session.execute(select(Site).where(Site.id == last_site_id))
        ).scalar_one_or_none()
        if site_obj is None or site_obj.archived_at is not None:
            await message.answer(t("quick_start_no_history"))
            return
        # Confirm the last-used site is still in the user's visible scope
        # (worker may have switched crews; old personal site no longer counts).
        if db_user is not None:
            owner_id = await resolve_effective_site_owner_id(session, db_user)
            if owner_id is None or site_obj.user_id != owner_id:
                await message.answer(t("quick_start_no_history"))
                return
        site_name = site_obj.name
        await state.update_data(user_db_id=user.id, site_id=last_site_id)

    await message.answer(
        t("quick_start_using_site", site=site_name or "—"),
        reply_markup=location_request(),
    )
    await state.set_state(ShiftStart.awaiting_location)


@router.message(F.text.contains("Начать смену"))
async def handle_start_shift(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    assert message.from_user is not None
    async for session in get_session():
        from src.services.shifts import ensure_user

        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        open_shift = await get_open_shift(session, user.id)

        if open_shift is not None:
            start_time = open_shift.start_at.strftime("%H:%M")
            site_name = "—"
            if open_shift.site_id:
                from src.core.models import Site

                res = await session.execute(select(Site).where(Site.id == open_shift.site_id))
                site_obj = res.scalar_one_or_none()
                if site_obj:
                    site_name = site_obj.name
            await message.answer(
                t("shift_already_open", start_time=start_time, site=site_name),
                reply_markup=main_menu(),
            )
            return

        # Sites visible for clock-in: own (owner/foreman) or crew foreman's (worker).
        sites = (
            await get_visible_sites_for_user(session, db_user)
            if db_user is not None
            else []
        )
        await state.update_data(user_db_id=user.id)

    await message.answer(t("select_site"), reply_markup=site_selection(sites))
    await state.set_state(ShiftStart.selecting_site)


@router.callback_query(ShiftStart.selecting_site, F.data.startswith("site:"))
async def handle_site_selected(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.data is not None
    assert callback.message is not None

    site_value = callback.data.split(":")[1]

    if site_value == "new":
        await callback.message.answer(t("enter_site_name"))
        await state.set_state(ShiftStart.entering_site_name)
    else:
        site_id = int(site_value)
        await state.update_data(site_id=site_id)
        await callback.message.answer(
            t("send_location"), reply_markup=location_request(),
        )
        await state.set_state(ShiftStart.awaiting_location)

    await callback.answer()


@router.message(ShiftStart.entering_site_name)
async def handle_new_site_name(
    message: Message, state: FSMContext, db_user: User | None = None,
) -> None:
    assert message.text is not None
    assert message.from_user is not None

    data = await state.get_data()
    user_db_id: int = data["user_db_id"]

    site_id: int
    async for session in get_session():
        # Owner of the new site = effective scope owner (foreman for workers in a crew).
        owner_id: int | None = user_db_id
        if db_user is not None:
            resolved = await resolve_effective_site_owner_id(session, db_user)
            if resolved is not None:
                owner_id = resolved
        if owner_id is None:
            await message.answer(t("no_crew"))
            await state.clear()
            return
        site = await create_site(session, owner_id, message.text.strip())
        await session.commit()
        site_id = site.id

    await state.update_data(site_id=site_id)
    await message.answer(t("site_created", name=message.text.strip()))
    await message.answer(t("send_location"), reply_markup=location_request())
    await state.set_state(ShiftStart.awaiting_location)


@router.message(ShiftStart.awaiting_location, F.location)
async def handle_start_location(message: Message, state: FSMContext) -> None:
    assert message.location is not None
    assert message.from_user is not None

    data = await state.get_data()
    user_db_id: int = data["user_db_id"]
    site_id: int | None = data.get("site_id")
    lat = message.location.latitude
    lon = message.location.longitude
    location_wkt = f"POINT({lon} {lat})"

    async for session in get_session():
        # Geofence check
        if site_id is not None:
            inside = await check_point_in_site(session, site_id, lon, lat)
            if inside is False:
                await message.answer(f"\u26a0 {t('location_outside_warning')}")

        try:
            shift = await start_shift(session, user_db_id, site_id, location_wkt)
            await session.commit()
        except ShiftAlreadyOpenError:
            await message.answer(t("integrity_error"), reply_markup=main_menu())
            await state.clear()
            return

        # Get site name for summary
        site_name = "—"
        if site_id:
            from sqlalchemy import select

            from src.core.models import Site

            res = await session.execute(select(Site).where(Site.id == site_id))
            site_obj = res.scalar_one_or_none()
            if site_obj:
                site_name = site_obj.name

    start_time = shift.start_at.strftime("%H:%M")
    await state.update_data(shift_id=shift.id)
    await message.answer(
        t("shift_started", time=start_time, site=site_name),
    )
    await message.answer(t("send_photo_or_skip"), reply_markup=skip_photo())
    await state.set_state(ShiftStart.awaiting_photo)


@router.message(ShiftStart.awaiting_photo, F.photo)
async def handle_start_photo(message: Message, state: FSMContext) -> None:
    assert message.photo is not None
    assert message.bot is not None

    data = await state.get_data()
    shift_id: int = data["shift_id"]
    file_id = message.photo[-1].file_id

    settings = get_settings()
    storage_path = await archive_shift_photo(
        message.bot, settings, shift_id, "start", file_id,
    )

    async for session in get_session():
        from sqlalchemy import select

        from src.core.models import Shift

        res = await session.execute(select(Shift).where(Shift.id == shift_id))
        shift = res.scalar_one()
        shift.start_photo_file_id = file_id
        if storage_path is not None:
            shift.start_photo_path = storage_path
        await session.commit()

    await message.answer(t("photo_saved"), reply_markup=main_menu())
    await state.clear()


@router.message(ShiftStart.awaiting_photo, F.text)
async def handle_start_photo_skip(message: Message, state: FSMContext) -> None:
    await message.answer("OK", reply_markup=main_menu())
    await state.clear()


# --- STOP SHIFT ---


@router.message(F.text.contains("Закончить смену"))
async def handle_stop_shift(message: Message, state: FSMContext) -> None:
    assert message.from_user is not None

    async for session in get_session():
        from src.services.shifts import ensure_user

        user = await ensure_user(session, message.from_user.id, message.from_user.full_name)
        open_shift = await get_open_shift(session, user.id)

        if open_shift is None:
            await message.answer(t("no_open_shift"), reply_markup=main_menu())
            return

        site_name = "—"
        if open_shift.site_id:
            from sqlalchemy import select

            from src.core.models import Site

            res = await session.execute(select(Site).where(Site.id == open_shift.site_id))
            site_obj = res.scalar_one_or_none()
            if site_obj:
                site_name = site_obj.name

        start_time = open_shift.start_at.strftime("%H:%M")
        await state.update_data(user_db_id=user.id, shift_id=open_shift.id, site_name=site_name)

    await message.answer(
        t("confirm_stop", site=site_name, start_time=start_time),
        reply_markup=confirm_stop(),
    )
    await state.set_state(ShiftStop.confirming)


@router.callback_query(ShiftStop.confirming, F.data == "stop:confirm")
async def handle_stop_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.message is not None
    await callback.message.answer(
        t("send_end_location"), reply_markup=location_request(),
    )
    await state.set_state(ShiftStop.awaiting_end_location)
    await callback.answer()


@router.callback_query(ShiftStop.confirming, F.data == "stop:cancel")
async def handle_stop_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    assert callback.message is not None
    await state.clear()
    await callback.message.answer(t("cancelled"), reply_markup=main_menu())
    await callback.answer()


@router.message(ShiftStop.awaiting_end_location, F.location)
async def handle_end_location(message: Message, state: FSMContext) -> None:
    assert message.location is not None

    data = await state.get_data()
    shift_id: int = data["shift_id"]
    site_name: str = data.get("site_name", "—")
    lat = message.location.latitude
    lon = message.location.longitude
    location_wkt = f"POINT({lon} {lat})"

    async for session in get_session():
        from sqlalchemy import select

        from src.core.models import Shift

        res = await session.execute(select(Shift).where(Shift.id == shift_id))
        shift = res.scalar_one()
        shift = await stop_shift(session, shift, location_wkt)
        await session.commit()

        assert shift.end_at is not None
        from decimal import Decimal as Dec

        gross_hours = compute_hours(shift.start_at, shift.end_at)
        shift_breaks = await get_breaks_for_shift(session, shift.id)
        break_h = total_break_hours(shift_breaks, shift.start_at, shift.end_at)
        net = gross_hours - break_h
        if net < Dec(0):
            net = Dec(0)
        hours = net.quantize(Dec("0.01"))

        # Check if we can compute amount
        rate = None
        if shift.site_id:
            from src.core.models import Site as SiteModel

            site_res = await session.execute(select(SiteModel).where(SiteModel.id == shift.site_id))
            site_obj = site_res.scalar_one_or_none()
            if site_obj and site_obj.hourly_rate:
                rate = site_obj.hourly_rate

        if rate is None:
            from src.core.models import User

            user_res = await session.execute(select(User).where(User.id == shift.user_id))
            user_obj = user_res.scalar_one_or_none()
            if user_obj and user_obj.hourly_rate:
                rate = user_obj.hourly_rate

    await state.update_data(shift_id=shift_id)

    if rate:
        amount = hours * rate
        amt_str = str(amount.quantize(Dec("0.01")))
        await message.answer(
            t("shift_stopped_with_amount",
              hours=str(hours), site=site_name, amount=amt_str),
        )
    else:
        await message.answer(t("shift_stopped", hours=str(hours), site=site_name))

    await message.answer(t("send_photo_or_skip"), reply_markup=skip_photo())
    await state.set_state(ShiftStop.awaiting_end_photo)


@router.message(ShiftStop.awaiting_end_photo, F.photo)
async def handle_end_photo(message: Message, state: FSMContext) -> None:
    assert message.photo is not None
    assert message.bot is not None

    data = await state.get_data()
    shift_id: int = data["shift_id"]
    file_id = message.photo[-1].file_id

    settings = get_settings()
    storage_path = await archive_shift_photo(
        message.bot, settings, shift_id, "end", file_id,
    )

    async for session in get_session():
        from sqlalchemy import select

        from src.core.models import Shift

        res = await session.execute(select(Shift).where(Shift.id == shift_id))
        shift = res.scalar_one()
        shift.end_photo_file_id = file_id
        if storage_path is not None:
            shift.end_photo_path = storage_path
        await session.commit()

    await message.answer(t("photo_saved"), reply_markup=main_menu())
    await state.clear()


@router.message(ShiftStop.awaiting_end_photo, F.text)
async def handle_end_photo_skip(message: Message, state: FSMContext) -> None:
    await message.answer("OK", reply_markup=main_menu())
    await state.clear()
