"""Phase 6.6: recorded salary payment ledger.

A `SalaryPayment` records both *when* money was paid out (`paid_on`) and
*which accounting period* it covers (`period_year` + `period_month`).
These typically differ — e.g. salary for April is paid in early May —
so storing them as two distinct fields is the only way to keep the
books honest.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import SalaryPayment


def _validate_period(year: int, month: int) -> None:
    if not (1 <= month <= 12):
        raise ValueError("period_month must be in 1..12")
    if not (2000 <= year <= 2100):
        raise ValueError("period_year out of range")


async def record_payment(
    session: AsyncSession,
    *,
    user_id: int,
    paid_on: date,
    period_year: int,
    period_month: int,
    amount: Decimal,
    recorded_by_id: int,
    note: str | None = None,
) -> SalaryPayment:
    _validate_period(period_year, period_month)
    if amount <= 0:
        raise ValueError("amount must be positive")
    payment = SalaryPayment(
        user_id=user_id,
        paid_on=paid_on,
        period_year=period_year,
        period_month=period_month,
        amount=amount,
        recorded_by_id=recorded_by_id,
        note=note,
    )
    session.add(payment)
    await session.flush()
    return payment


async def list_payments_paid_on(
    session: AsyncSession, *, user_id: int, day: date,
) -> list[SalaryPayment]:
    """All payments physically paid on a specific date (one user)."""
    return list(
        (
            await session.execute(
                select(SalaryPayment)
                .where(
                    SalaryPayment.user_id == user_id,
                    SalaryPayment.paid_on == day,
                )
                .order_by(desc(SalaryPayment.id)),
            )
        ).scalars().all(),
    )


async def list_payments_paid_in_range(
    session: AsyncSession, *, user_id: int, start: date, end: date,
) -> list[SalaryPayment]:
    """All payments where paid_on is in the inclusive range."""
    return list(
        (
            await session.execute(
                select(SalaryPayment)
                .where(
                    SalaryPayment.user_id == user_id,
                    SalaryPayment.paid_on >= start,
                    SalaryPayment.paid_on <= end,
                )
                .order_by(desc(SalaryPayment.paid_on), desc(SalaryPayment.id)),
            )
        ).scalars().all(),
    )


async def list_payments_for_period(
    session: AsyncSession,
    *,
    user_id: int,
    period_year: int,
    period_month: int,
) -> list[SalaryPayment]:
    """All payments whose accounting period equals the given year+month."""
    return list(
        (
            await session.execute(
                select(SalaryPayment)
                .where(
                    SalaryPayment.user_id == user_id,
                    SalaryPayment.period_year == period_year,
                    SalaryPayment.period_month == period_month,
                )
                .order_by(desc(SalaryPayment.paid_on), desc(SalaryPayment.id)),
            )
        ).scalars().all(),
    )
