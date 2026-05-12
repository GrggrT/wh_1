"""Phase 6.11a: text renderer for ``ReportData``."""

from __future__ import annotations

from decimal import Decimal

from src.bot.strings import t
from src.core.models import User
from src.services.day_entries import format_hours
from src.services.reports.service import ReportData

_RU_MONTHS: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)


def _fmt_money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _status_tag(status: str) -> str:
    if status == "settled":
        return t("report_tag_settled")
    if status == "pending":
        return t("report_tag_pending")
    if status == "partial":
        return t("report_tag_partial")
    if status == "overpaid":
        return t("report_tag_overpaid")
    return t("report_tag_unpriced")


def format_report_text(data: ReportData, user: User) -> str:
    cur = user.currency
    lines: list[str] = [t("report_header", months=data.months)]
    for led in data.ledgers:
        period = f"{_RU_MONTHS[led.month - 1]} {led.year}"
        if led.status == "unpriced":
            lines.append(
                t(
                    "report_row_unpriced",
                    period=period,
                    hours=format_hours(led.hours),
                ),
            )
            continue
        remaining = led.remaining if led.remaining is not None else Decimal(0)
        lines.append(
            t(
                "report_row",
                period=period,
                hours=format_hours(led.hours),
                earned=_fmt_money(led.earnings),
                received=_fmt_money(led.received_total),
                remaining=_fmt_money(remaining),
                currency=cur,
                tag=_status_tag(led.status),
            ),
        )

    lines.append("")
    lines.append(
        t(
            "report_totals",
            hours=format_hours(data.total_hours),
            earned=_fmt_money(data.total_earnings),
            received=_fmt_money(data.total_received),
            owed=_fmt_money(data.total_owed),
            currency=cur,
        ),
    )
    if data.total_overpaid > 0:
        lines.append(
            t(
                "report_total_overpaid",
                overpaid=_fmt_money(data.total_overpaid),
                currency=cur,
            ),
        )
    return "\n".join(lines)
