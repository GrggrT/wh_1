"""Break (lunch / pause) tracking within an open shift."""

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Break, Shift


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
