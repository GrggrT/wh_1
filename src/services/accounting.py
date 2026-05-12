"""Phase 6.7: period-vs-cashflow accounting view.

Bridges the three primitives (DayEntry, Advance, SalaryPayment) into a single
``PeriodLedger`` so the bot can show "how much did I earn for month M, and
how much has been received against it so far?" without confusion when the
cash arrives in a later calendar month.

Key invariants
~~~~~~~~~~~~~~
- ``period_year`` + ``period_month`` always identify the work period the
  cash covers (independent of when cash was paid).
- ``Advance.day`` is the physical cash date; ``Advance.period_year`` +
  ``Advance.period_month`` is the work period it counts against. They
  default to the same calendar month but can legitimately differ — e.g.
  an advance handed over on May 5 for April work (Phase 6.10b).
- ``SalaryPayment`` separates ``paid_on`` from period in the same way.

Status values
~~~~~~~~~~~~~
- ``unpriced``: no hourly rate available → earnings unknown.
- ``pending``:  earnings > 0, nothing received yet.
- ``partial``:  some received, but remaining > settled threshold.
- ``settled``:  |remaining| < settled threshold (covers copeck rounding).
- ``overpaid``: received > earnings beyond the settled threshold.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Advance, SalaryPayment, User
from src.services.advances import compute_salary, month_bounds

# Rounding tolerance for settlement: copeck-level differences shouldn't
# leave a period flagged "partial".
SETTLED_THRESHOLD = Decimal("1.00")


def _prev_year_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


@dataclass
class PeriodLedger:
    """All accounting facts for one (user, year, month)."""

    user_id: int
    year: int
    month: int
    hours: Decimal
    earnings: Decimal | None
    advances: list[Advance] = field(default_factory=list)
    payments: list[SalaryPayment] = field(default_factory=list)

    @property
    def advances_total(self) -> Decimal:
        return sum(
            (a.amount for a in self.advances), Decimal(0),
        ).quantize(Decimal("0.01"))

    @property
    def payments_total(self) -> Decimal:
        return sum(
            (p.amount for p in self.payments), Decimal(0),
        ).quantize(Decimal("0.01"))

    @property
    def received_total(self) -> Decimal:
        return (self.advances_total + self.payments_total).quantize(
            Decimal("0.01"),
        )

    @property
    def remaining(self) -> Decimal | None:
        """Earnings − received. ``None`` when earnings can't be priced."""
        if self.earnings is None:
            return None
        return (self.earnings - self.received_total).quantize(Decimal("0.01"))

    @property
    def status(self) -> str:
        if self.earnings is None:
            return "unpriced"
        remaining = self.remaining
        assert remaining is not None
        if abs(remaining) < SETTLED_THRESHOLD:
            return "settled"
        if remaining > 0:
            if self.received_total == 0:
                return "pending"
            return "partial"
        return "overpaid"


@dataclass
class CashflowEntry:
    """One physical-cash event (advance or payment) on a specific day."""

    kind: str  # "advance" or "payment"
    day: date
    amount: Decimal
    period_year: int
    period_month: int
    note: str | None


async def get_period_ledger(
    session: AsyncSession,
    *,
    user: User,
    year: int,
    month: int,
    tz: ZoneInfo,
) -> PeriodLedger:
    """Build the ledger for one (user, period).

    Earnings are reused from ``compute_salary`` so any future change to the
    pricing logic (site rates, breaks, etc.) flows through here for free.
    Both advances and payments are pulled by their declared
    ``period_year`` + ``period_month`` — cash paid in a different calendar
    month attributes back to the work period it covers.
    """
    breakdown = await compute_salary(
        session, user=user, year=year, month=month, tz=tz,
    )
    first_day, last_day = month_bounds(year, month)

    advances = list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id == user.id,
                    Advance.period_year == year,
                    Advance.period_month == month,
                )
                .order_by(desc(Advance.day), desc(Advance.id)),
            )
        ).scalars().all(),
    )
    payments = list(
        (
            await session.execute(
                select(SalaryPayment)
                .where(
                    SalaryPayment.user_id == user.id,
                    SalaryPayment.period_year == year,
                    SalaryPayment.period_month == month,
                )
                .order_by(desc(SalaryPayment.paid_on), desc(SalaryPayment.id)),
            )
        ).scalars().all(),
    )

    return PeriodLedger(
        user_id=user.id,
        year=year,
        month=month,
        hours=breakdown.total_hours,
        earnings=breakdown.total_earnings,
        advances=advances,
        payments=payments,
    )


async def list_cashflow(
    session: AsyncSession,
    *,
    user: User,
    start: date,
    end: date,
) -> list[CashflowEntry]:
    """Every cash event between ``start`` and ``end`` (inclusive), newest first.

    Both advances and payments carry their declared accounting period,
    which may differ from the cash date (Phase 6.10b for advances).
    """
    advances = list(
        (
            await session.execute(
                select(Advance)
                .where(
                    Advance.user_id == user.id,
                    Advance.day >= start,
                    Advance.day <= end,
                ),
            )
        ).scalars().all(),
    )
    payments = list(
        (
            await session.execute(
                select(SalaryPayment)
                .where(
                    SalaryPayment.user_id == user.id,
                    SalaryPayment.paid_on >= start,
                    SalaryPayment.paid_on <= end,
                ),
            )
        ).scalars().all(),
    )
    entries: list[CashflowEntry] = []
    for a in advances:
        entries.append(
            CashflowEntry(
                kind="advance",
                day=a.day,
                amount=a.amount,
                period_year=a.period_year,
                period_month=a.period_month,
                note=a.note,
            ),
        )
    for p in payments:
        entries.append(
            CashflowEntry(
                kind="payment",
                day=p.paid_on,
                amount=p.amount,
                period_year=p.period_year,
                period_month=p.period_month,
                note=p.note,
            ),
        )
    # Newest first, payments before advances on a tie (cosmetic; both valid).
    entries.sort(key=lambda e: (e.day, 0 if e.kind == "payment" else 1), reverse=True)
    return entries


async def list_open_periods(
    session: AsyncSession,
    *,
    user: User,
    tz: ZoneInfo,
    today: date,
    lookback_months: int = 12,
) -> list[PeriodLedger]:
    """Return ledgers for the last ``lookback_months`` periods that are
    still owed (pending or partial). Newest period first.
    """
    year, month = today.year, today.month
    open_ledgers: list[PeriodLedger] = []
    for _ in range(lookback_months):
        ledger = await get_period_ledger(
            session, user=user, year=year, month=month, tz=tz,
        )
        if ledger.status in ("pending", "partial"):
            open_ledgers.append(ledger)
        year, month = _prev_year_month(year, month)
    return open_ledgers
