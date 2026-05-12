"""Cross-account backup transfer via one-shot share tokens.

Issue side (``/share_backup``): the caller mints a row in ``share_tokens``
that authorizes another Telegram account to import the caller's data.
The token is short-lived (TTL hours) and single-use.

Redeem side (``/restore_from <token>``): the recipient presents the
token; if it's valid (exists, not expired, not redeemed), we pull the
source user's data live and run :func:`apply_restore` against the
recipient's tables. The token is then marked redeemed.

Live read at redeem time means the source user can amend their data up
until the moment the recipient claims it — there's no XLSX snapshot
between the two events.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.models import Advance, DayEntry, SalaryPayment, ShareToken, User
from src.services.reports.restore import (
    AdvanceRow,
    DayEntryRow,
    PaymentRow,
    RestorePlan,
    RestoreResult,
    apply_restore,
)

# 24 hours by default — long enough for the recipient to be on hand,
# short enough to not leave a foot-gun lying around.
DEFAULT_TTL = timedelta(hours=24)


class ShareTokenError(ValueError):
    """Raised when a presented token is invalid, expired, or already used."""


@dataclass
class IssuedToken:
    token: str
    expires_at: datetime


async def issue_share_token(
    session: AsyncSession,
    *,
    source_user: User,
    ttl: timedelta = DEFAULT_TTL,
    now: datetime | None = None,
    max_active: int | None = None,
) -> IssuedToken:
    moment = now or datetime.now(tz=UTC)
    if max_active is not None:
        active = (
            await session.execute(
                select(func.count())
                .select_from(ShareToken)
                .where(
                    ShareToken.source_user_id == source_user.id,
                    ShareToken.redeemed_at.is_(None),
                    ShareToken.expires_at > moment,
                ),
            )
        ).scalar_one()
        if active >= max_active:
            raise ShareTokenError("rate_limited")
    raw = secrets.token_urlsafe(24)
    row = ShareToken(
        token=raw,
        source_user_id=source_user.id,
        expires_at=moment + ttl,
    )
    session.add(row)
    await session.flush()
    return IssuedToken(token=raw, expires_at=row.expires_at)


async def _build_plan_for_user(
    session: AsyncSession, *, source_user: User,
) -> RestorePlan:
    days_rows = (
        await session.execute(
            select(DayEntry)
            .where(DayEntry.user_id == source_user.id)
            .order_by(DayEntry.day),
        )
    ).scalars().all()
    adv_rows = (
        await session.execute(
            select(Advance)
            .where(Advance.user_id == source_user.id)
            .order_by(Advance.day),
        )
    ).scalars().all()
    pay_rows = (
        await session.execute(
            select(SalaryPayment)
            .where(SalaryPayment.user_id == source_user.id)
            .order_by(SalaryPayment.paid_on),
        )
    ).scalars().all()
    return RestorePlan(
        days=[
            DayEntryRow(day=r.day, hours=r.hours, note=r.note)
            for r in days_rows
        ],
        advances=[
            AdvanceRow(
                day=r.day,
                period_year=r.period_year,
                period_month=r.period_month,
                amount=r.amount,
                note=r.note,
            )
            for r in adv_rows
        ],
        payments=[
            PaymentRow(
                paid_on=r.paid_on,
                period_year=r.period_year,
                period_month=r.period_month,
                amount=r.amount,
                note=r.note,
            )
            for r in pay_rows
        ],
    )


async def _validate_token(
    session: AsyncSession, *, token: str, redeemer: User, moment: datetime,
) -> tuple[ShareToken, User]:
    row = (
        await session.execute(
            select(ShareToken).where(ShareToken.token == token),
        )
    ).scalar_one_or_none()
    if row is None:
        raise ShareTokenError("not_found")
    if row.redeemed_at is not None:
        raise ShareTokenError("already_redeemed")
    expires = row.expires_at
    if expires.tzinfo is None:  # sqlite round-trip drops tzinfo
        expires = expires.replace(tzinfo=UTC)
    if expires <= moment:
        raise ShareTokenError("expired")
    if row.source_user_id == redeemer.id:
        raise ShareTokenError("same_user")

    source_user = (
        await session.execute(
            select(User).where(User.id == row.source_user_id),
        )
    ).scalar_one_or_none()
    if source_user is None:
        raise ShareTokenError("source_missing")
    return row, source_user


async def peek_share_token(
    session: AsyncSession,
    *,
    token: str,
    redeemer: User,
    now: datetime | None = None,
) -> RestorePlan:
    """Validate ``token`` and build the source user's plan WITHOUT consuming.

    Used by the /restore_from confirm-step preview: counts are shown,
    user confirms, then :func:`redeem_share_token` re-validates and applies.
    """
    moment = now or datetime.now(tz=UTC)
    _row, source_user = await _validate_token(
        session, token=token, redeemer=redeemer, moment=moment,
    )
    return await _build_plan_for_user(session, source_user=source_user)


async def redeem_share_token(
    session: AsyncSession,
    *,
    token: str,
    redeemer: User,
    now: datetime | None = None,
) -> RestoreResult:
    moment = now or datetime.now(tz=UTC)
    row, source_user = await _validate_token(
        session, token=token, redeemer=redeemer, moment=moment,
    )
    plan = await _build_plan_for_user(session, source_user=source_user)
    result = await apply_restore(session, user=redeemer, plan=plan)
    row.redeemed_at = moment
    row.redeemed_by_user_id = redeemer.id
    await session.flush()
    return result
