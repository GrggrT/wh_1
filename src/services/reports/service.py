"""Phase 6.11a: ``ReportData`` — multi-month period summary.

A ``ReportData`` rolls up the last N ``PeriodLedger`` objects into a
single view: hours/earnings totals, total received, total owed, plus
the per-period rows. Formatting (text/XLSX/PDF/PNG) is layered on top —
this module only does the data fetch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import User
from src.services.accounting import PeriodLedger, get_period_ledger


def _prev_year_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


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
    """Build the rolling-N-month report ending at ``today``'s month."""
    year, month = today.year, today.month
    ledgers: list[PeriodLedger] = []
    for _ in range(months):
        led = await get_period_ledger(
            session, user=user, year=year, month=month, tz=tz,
        )
        ledgers.append(led)
        year, month = _prev_year_month(year, month)
    return ReportData(user_id=user.id, months=months, ledgers=ledgers)
