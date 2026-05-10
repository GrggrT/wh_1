"""Shift edit / delete with audit logging."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import AuditLog, Shift, Site, User


class ShiftEditError(Exception):
    pass


EDITABLE_FIELDS = ("start", "end", "note", "work_type", "site")


def parse_local_datetime(raw: str, tz: ZoneInfo) -> datetime:
    """Parse 'YYYY-MM-DD HH:MM' in tz; return tz-aware UTC datetime."""
    dt = datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M")
    local = dt.replace(tzinfo=tz)
    return local.astimezone(ZoneInfo("UTC"))


def _serialize_shift(shift: Shift) -> dict[str, object]:
    return {
        "id": shift.id,
        "user_id": shift.user_id,
        "site_id": shift.site_id,
        "start_at": shift.start_at.isoformat() if shift.start_at else None,
        "end_at": shift.end_at.isoformat() if shift.end_at else None,
        "note": shift.note,
        "work_type": shift.work_type,
    }


async def list_recent_shifts(
    session: AsyncSession,
    user_id: int,
    days: int = 14,
    limit: int = 20,
) -> list[Shift]:
    cutoff = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=days)
    stmt = (
        select(Shift)
        .where(Shift.user_id == user_id, Shift.start_at >= cutoff)
        .order_by(Shift.start_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_recent_crew_shifts(
    session: AsyncSession,
    crew_id: int,
    days: int = 14,
    limit: int = 30,
) -> list[Shift]:
    """Recent shifts by all members of a crew (joined via User.crew_id)."""
    cutoff = datetime.now(tz=ZoneInfo("UTC")) - timedelta(days=days)
    stmt = (
        select(Shift)
        .join(User, User.id == Shift.user_id)
        .where(User.crew_id == crew_id, Shift.start_at >= cutoff)
        .order_by(Shift.start_at.desc())
        .limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_shift(session: AsyncSession, shift_id: int) -> Shift | None:
    return (
        await session.execute(select(Shift).where(Shift.id == shift_id))
    ).scalar_one_or_none()


async def update_shift_field(
    session: AsyncSession,
    actor: User,
    shift: Shift,
    field: str,
    value: str,
    tz: ZoneInfo,
) -> dict[str, object]:
    """Apply a single-field edit; return {before, after} for the changed field."""
    if field not in EDITABLE_FIELDS:
        raise ShiftEditError("invalid_field")

    before: object
    after: object

    if field == "start":
        before = shift.start_at.isoformat()
        new_dt = parse_local_datetime(value, tz)
        if shift.end_at is not None and new_dt >= shift.end_at:
            raise ShiftEditError("start_after_end")
        shift.start_at = new_dt
        after = new_dt.isoformat()
    elif field == "end":
        before = shift.end_at.isoformat() if shift.end_at else None
        new_dt = parse_local_datetime(value, tz)
        if new_dt <= shift.start_at:
            raise ShiftEditError("end_before_start")
        shift.end_at = new_dt
        after = new_dt.isoformat()
    elif field == "note":
        before = shift.note
        shift.note = value or None
        after = shift.note
    elif field == "work_type":
        before = shift.work_type
        shift.work_type = value or None
        after = shift.work_type
    else:  # site
        try:
            site_id = int(value)
        except ValueError as exc:
            raise ShiftEditError("invalid_site") from exc
        site = (
            await session.execute(select(Site).where(Site.id == site_id))
        ).scalar_one_or_none()
        if site is None:
            raise ShiftEditError("site_not_found")
        before = shift.site_id
        shift.site_id = site_id
        after = site_id

    diff: dict[str, object] = {field: {"before": before, "after": after}}
    session.add(
        AuditLog(
            user_id=actor.id,
            entity_type="shift",
            entity_id=shift.id,
            action="edit",
            diff=diff,
        ),
    )
    await session.flush()
    return diff


async def delete_shift(
    session: AsyncSession, actor: User, shift: Shift,
) -> None:
    snapshot = _serialize_shift(shift)
    session.add(
        AuditLog(
            user_id=actor.id,
            entity_type="shift",
            entity_id=shift.id,
            action="delete",
            diff={"snapshot": snapshot},
        ),
    )
    await session.delete(shift)
    await session.flush()


def format_shift_summary(
    shift: Shift,
    site_name: str | None,
    tz: ZoneInfo,
) -> str:
    """One-line summary for the /shifts listing."""
    local_start = shift.start_at.astimezone(tz)
    if shift.end_at is None:
        return f"#{shift.id} {local_start.strftime('%d.%m %H:%M')} — открыта ({site_name or '—'})"
    local_end = shift.end_at.astimezone(tz)
    delta = shift.end_at - shift.start_at
    hours = Decimal(int(delta.total_seconds())) / Decimal(3600)
    same_day = local_start.date() == local_end.date()
    end_str = (
        local_end.strftime("%H:%M") if same_day
        else local_end.strftime("%d.%m %H:%M")
    )
    return (
        f"#{shift.id} {local_start.strftime('%d.%m %H:%M')}–{end_str} "
        f"{hours.quantize(Decimal('0.01'))} ч ({site_name or '—'})"
    )


def today_in_tz(tz: ZoneInfo) -> date:
    return datetime.now(tz=tz).date()


__all__ = [
    "EDITABLE_FIELDS",
    "ShiftEditError",
    "delete_shift",
    "format_shift_summary",
    "get_shift",
    "list_recent_shifts",
    "parse_local_datetime",
    "today_in_tz",
    "update_shift_field",
]
