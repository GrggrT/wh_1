"""Phase 6.11a: ``ReportData`` — multi-month period summary.

A ``ReportData`` rolls up the last N ``PeriodLedger`` objects into a
single view: hours/earnings totals, total received, total owed, plus
the per-period rows. Formatting (text/XLSX/PDF/PNG) is layered on top —
this module only does the data fetch.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Advance, SalaryPayment, User
from src.services.accounting import PeriodLedger, get_period_ledger


def _prev_year_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def _period_keys(year: int, month: int, months: int) -> list[tuple[int, int]]:
    """List of (year, month) keys, newest first, of length ``months``."""
    keys: list[tuple[int, int]] = []
    y, m = year, month
    for _ in range(months):
        keys.append((y, m))
        y, m = _prev_year_month(y, m)
    return keys


@dataclass
class ReportData:
    """N-month rolling report for one user. ``ledgers`` is newest first."""

    user_id: int
    months: int
    ledgers: list[PeriodLedger]

    @property
    def total_hours(self) -> Decimal:
        return sum(
            (lg.hours for lg in self.ledgers), Decimal(0),
        ).quantize(Decimal("0.01"))

    @property
    def total_earnings(self) -> Decimal | None:
        priced = [lg.earnings for lg in self.ledgers if lg.earnings is not None]
        if not priced:
            return None
        return sum(priced, Decimal(0)).quantize(Decimal("0.01"))

    @property
    def total_received(self) -> Decimal:
        return sum(
            (lg.received_total for lg in self.ledgers), Decimal(0),
        ).quantize(Decimal("0.01"))

    @property
    def total_owed(self) -> Decimal:
        """Sum of positive remainings — work done but not yet paid."""
        owed = Decimal(0)
        for lg in self.ledgers:
            r = lg.remaining
            if r is not None and r > 0:
                owed += r
        return owed.quantize(Decimal("0.01"))

    @property
    def total_overpaid(self) -> Decimal:
        """Sum of |negative remainings| — money received above earnings."""
        over = Decimal(0)
        for lg in self.ledgers:
            r = lg.remaining
            if r is not None and r < 0:
                over += -r
        return over.quantize(Decimal("0.01"))


async def get_report_data(
    session: AsyncSession,
    *,
    user: User,
    tz: ZoneInfo,
    today: date,
    months: int = 6,
) -> ReportData:
    """Build the rolling-N-month report ending at ``today``'s month.

    Advances and salary payments for the whole window are fetched in a
    single round-trip each and sliced per period, dropping 2 queries per
    month vs. the naive loop. Earnings still go through ``compute_salary``
    per month so that the shifts/sites/breaks logic stays in one place.
    """
    keys = _period_keys(today.year, today.month, months)
    key_set = set(keys)

    advances_by_period: dict[tuple[int, int], list[Advance]] = defaultdict(list)
    payments_by_period: dict[tuple[int, int], list[SalaryPayment]] = defaultdict(list)

    adv_rows = (
        await session.execute(
            select(Advance).where(Advance.user_id == user.id),
        )
    ).scalars().all()
    for a in adv_rows:
        key = (a.period_year, a.period_month)
        if key in key_set:
            advances_by_period[key].append(a)

    pay_rows = (
        await session.execute(
            select(SalaryPayment).where(SalaryPayment.user_id == user.id),
        )
    ).scalars().all()
    for p in pay_rows:
        key = (p.period_year, p.period_month)
        if key in key_set:
            payments_by_period[key].append(p)

    ledgers: list[PeriodLedger] = []
    for year, month in keys:
        led = await get_period_ledger(
            session, user=user, year=year, month=month, tz=tz,
            prefetched_advances=advances_by_period.get((year, month), []),
            prefetched_payments=payments_by_period.get((year, month), []),
        )
        ledgers.append(led)
    return ReportData(user_id=user.id, months=months, ledgers=ledgers)
