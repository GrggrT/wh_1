"""Break (lunch / pause) tracking within an open shift."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Break, Shift


class BreakEditError(Exception):
    pass


BREAK_EDITABLE_FIELDS = ("start", "end")


class BreakError(Exception):
    pass


async def get_open_break(session: AsyncSession, shift_id: int) -> Break | None:
    stmt = select(Break).where(
        Break.shift_id == shift_id, Break.end_at.is_(None),
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def start_break(
    session: AsyncSession, shift: Shift, now: datetime | None = None,
) -> Break:
    if shift.end_at is not None:
        raise BreakError("shift_closed")
    open_break = await get_open_break(session, shift.id)
    if open_break is not None:
        raise BreakError("already_on_break")
    current = now or datetime.now(tz=UTC)
    new_break = Break(shift_id=shift.id, start_at=current)
    session.add(new_break)
    await session.flush()
    return new_break


async def stop_break(
    session: AsyncSession, shift_id: int, now: datetime | None = None,
) -> Break:
    open_break = await get_open_break(session, shift_id)
    if open_break is None:
        raise BreakError("no_open_break")
    open_break.end_at = now or datetime.now(tz=UTC)
    await session.flush()
    return open_break


async def find_stale_open_breaks(
    session: AsyncSession,
    max_break_hours: float,
    now: datetime | None = None,
) -> list[Break]:
    """Return open breaks running longer than `max_break_hours`."""
    current = now or datetime.now(tz=UTC)
    cutoff_seconds = max_break_hours * 3600
    rows = list((await session.execute(
        select(Break).where(Break.end_at.is_(None)),
    )).scalars().all())
    stale: list[Break] = []
    for b in rows:
        if (current - b.start_at).total_seconds() >= cutoff_seconds:
            stale.append(b)
    return stale


async def auto_close_break(
    session: AsyncSession, br: Break, now: datetime | None = None,
) -> Break:
    """Close a long-running break at start_at + max running time (or now)."""
    br.end_at = now or datetime.now(tz=UTC)
    await session.flush()
    return br


async def get_breaks_for_shift(
    session: AsyncSession, shift_id: int,
) -> list[Break]:
    stmt = (
        select(Break)
        .where(Break.shift_id == shift_id)
        .order_by(Break.start_at)
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_breaks_for_shifts(
    session: AsyncSession, shift_ids: list[int],
) -> dict[int, list[Break]]:
    if not shift_ids:
        return {}
    stmt = (
        select(Break)
        .where(Break.shift_id.in_(shift_ids))
        .order_by(Break.shift_id, Break.start_at)
    )
    rows = list((await session.execute(stmt)).scalars().all())
    by_shift: dict[int, list[Break]] = {sid: [] for sid in shift_ids}
    for b in rows:
        by_shift.setdefault(b.shift_id, []).append(b)
    return by_shift


async def get_break(session: AsyncSession, break_id: int) -> Break | None:
    return (
        await session.execute(select(Break).where(Break.id == break_id))
    ).scalar_one_or_none()


def _serialize_break(br: Break) -> dict[str, object]:
    return {
        "id": br.id,
        "shift_id": br.shift_id,
        "start_at": br.start_at.isoformat() if br.start_at else None,
        "end_at": br.end_at.isoformat() if br.end_at else None,
    }


def _check_break_window(
    shift: Shift, start_at: datetime, end_at: datetime,
) -> None:
    if end_at <= start_at:
        raise BreakEditError("end_before_start")
    if start_at < shift.start_at:
        raise BreakEditError("before_shift_start")
    if shift.end_at is not None and end_at > shift.end_at:
        raise BreakEditError("after_shift_end")


async def _check_break_overlap(
    session: AsyncSession,
    shift_id: int,
    start_at: datetime,
    end_at: datetime,
    exclude_break_id: int | None = None,
) -> None:
    existing = list((
        await session.execute(
            select(Break).where(Break.shift_id == shift_id),
        )
    ).scalars().all())
    for other in existing:
        if exclude_break_id is not None and other.id == exclude_break_id:
            continue
        other_end = other.end_at or datetime.now(tz=UTC)
        if start_at < other_end and other.start_at < end_at:
            raise BreakEditError("overlap")


async def create_manual_break(
    session: AsyncSession,
    shift: Shift,
    start_at: datetime,
    end_at: datetime,
) -> Break:
    """Create a closed break inside an existing shift's window."""
    _check_break_window(shift, start_at, end_at)
    await _check_break_overlap(session, shift.id, start_at, end_at)
    new_break = Break(shift_id=shift.id, start_at=start_at, end_at=end_at)
    session.add(new_break)
    await session.flush()
    return new_break


async def update_break_time(
    session: AsyncSession,
    br: Break,
    shift: Shift,
    field: str,
    new_value: datetime,
) -> dict[str, object]:
    """Update a break's start or end time. Returns {field: {before, after}}."""
    if field not in BREAK_EDITABLE_FIELDS:
        raise BreakEditError("invalid_field")
    if field == "start":
        before = br.start_at.isoformat()
        end_for_check = br.end_at or datetime.now(tz=UTC)
        _check_break_window(shift, new_value, end_for_check)
        await _check_break_overlap(
            session, shift.id, new_value, end_for_check, exclude_break_id=br.id,
        )
        br.start_at = new_value
        after = new_value.isoformat()
    else:  # end
        if br.end_at is None:
            raise BreakEditError("end_open_break")
        before = br.end_at.isoformat()
        _check_break_window(shift, br.start_at, new_value)
        await _check_break_overlap(
            session, shift.id, br.start_at, new_value, exclude_break_id=br.id,
        )
        br.end_at = new_value
        after = new_value.isoformat()
    await session.flush()
    return {field: {"before": before, "after": after}}


async def delete_break_row(session: AsyncSession, br: Break) -> dict[str, object]:
    """Delete a break, returning a snapshot for the audit log."""
    snapshot = _serialize_break(br)
    await session.delete(br)
    await session.flush()
    return {"snapshot": snapshot}


def total_break_hours(
    breaks: list[Break],
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> Decimal:
    """Sum closed break durations, optionally clipped to a [start, end] window."""
    total = Decimal(0)
    for b in breaks:
        if b.end_at is None:
            continue
        start = b.start_at
        end = b.end_at
        if window_start is not None and start < window_start:
            start = window_start
        if window_end is not None and end > window_end:
            end = window_end
        if end <= start:
            continue
        seconds = int((end - start).total_seconds())
        total += Decimal(seconds) / Decimal(3600)
    return total
