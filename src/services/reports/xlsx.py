"""Phase 6.11b: XLSX renderer for ``ReportData``.

Builds a single-sheet workbook with one row per period plus a totals row.
Money cells are written as floats with ``0.00`` number format so the
recipient can keep using Excel/Google Sheets formulas. Status is rendered
as the same emoji tag the text formatter uses, for at-a-glance parity.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from src.core.models import User
from src.services.reports.service import ReportData

_RU_MONTHS: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

_STATUS_TAGS: dict[str, str] = {
    "settled": "✅ закрыт",
    "pending": "⏳ ожидает",
    "partial": "🟡 частично",
    "overpaid": "🟢 переплата",
    "unpriced": "❔ без ставки",
}

_MONEY_FMT = "0.00"


def _money(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(value)


def build_report_xlsx(data: ReportData, user: User) -> BytesIO:
    """Render ``data`` into an in-memory ``.xlsx`` buffer."""
    cur = user.currency
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Отчёт"

    bold = Font(bold=True)
    centre = Alignment(horizontal="center")

    # Title row
    ws.cell(
        row=1, column=1,
        value=f"Отчёт за последние {data.months} мес.",
    ).font = bold

    # Header row
    headers = [
        "Период",
        "Часы",
        f"Начислено ({cur})",
        f"Получено ({cur})",
        f"Остаток ({cur})",
        "Статус",
    ]
    for col, label in enumerate(headers, 1):
        cell = ws.cell(row=3, column=col, value=label)
        cell.font = bold
        cell.alignment = centre

    # Per-period rows
    row_idx = 4
    for led in data.ledgers:
        period = f"{_RU_MONTHS[led.month - 1]} {led.year}"
        ws.cell(row=row_idx, column=1, value=period)

        hours_cell = ws.cell(row=row_idx, column=2, value=float(led.hours))
        hours_cell.number_format = _MONEY_FMT

        earned = _money(led.earnings)
        if earned is not None:
            c = ws.cell(row=row_idx, column=3, value=earned)
            c.number_format = _MONEY_FMT
        else:
            ws.cell(row=row_idx, column=3, value="—")

        received = _money(led.received_total)
        if received is not None:
            c = ws.cell(row=row_idx, column=4, value=received)
            c.number_format = _MONEY_FMT

        remaining = _money(led.remaining)
        if remaining is not None:
            c = ws.cell(row=row_idx, column=5, value=remaining)
            c.number_format = _MONEY_FMT
        else:
            ws.cell(row=row_idx, column=5, value="—")

        ws.cell(
            row=row_idx, column=6,
            value=_STATUS_TAGS.get(led.status, led.status),
        )
        row_idx += 1

    # Totals row
    total_row = row_idx + 1
    ws.cell(row=total_row, column=1, value="Итого").font = bold

    total_hours = ws.cell(
        row=total_row, column=2, value=float(data.total_hours),
    )
    total_hours.number_format = _MONEY_FMT
    total_hours.font = bold

    if data.total_earnings is not None:
        c = ws.cell(
            row=total_row, column=3, value=float(data.total_earnings),
        )
        c.number_format = _MONEY_FMT
        c.font = bold
    else:
        ws.cell(row=total_row, column=3, value="—").font = bold

    c = ws.cell(row=total_row, column=4, value=float(data.total_received))
    c.number_format = _MONEY_FMT
    c.font = bold

    c = ws.cell(row=total_row, column=5, value=float(data.total_owed))
    c.number_format = _MONEY_FMT
    c.font = bold
    ws.cell(row=total_row, column=6, value=f"долг ({cur})").font = bold

    if data.total_overpaid > 0:
        over_row = total_row + 1
        ws.cell(row=over_row, column=1, value="Переплата").font = bold
        c = ws.cell(
            row=over_row, column=5, value=float(data.total_overpaid),
        )
        c.number_format = _MONEY_FMT
        c.font = bold
        ws.cell(
            row=over_row, column=6, value=f"переплата ({cur})",
        ).font = bold

    # Sensible column widths
    widths = (18, 10, 16, 16, 16, 18)
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def xlsx_filename(months: int) -> str:
    return f"report_{months}m.xlsx"
