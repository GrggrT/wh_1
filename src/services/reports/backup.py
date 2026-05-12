"""Phase 7.1: full-data XLSX backup.

Dumps every row owned by a single user across the accounting tables
(``day_entries``, ``advances``, ``salary_payments``) plus a one-row profile
sheet, into a single ``.xlsx`` workbook. Pure render — the caller fetches
rows and passes them in.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from src.core.models import Advance, DayEntry, SalaryPayment, User

_MONEY_FMT = "0.00"
_DATE_FMT = "yyyy-mm-dd"


def _money(value: Decimal | None) -> float | None:
    return None if value is None else float(value)


def _write_header(ws, headers: tuple[str, ...]) -> None:  # noqa: ANN001
    bold = Font(bold=True)
    centre = Alignment(horizontal="center")
    for col, label in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=label)
        cell.font = bold
        cell.alignment = centre


def _set_widths(ws, widths: tuple[int, ...]) -> None:  # noqa: ANN001
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = width


def _fill_profile(ws, user: User, today: date) -> None:  # noqa: ANN001
    bold = Font(bold=True)
    rows: list[tuple[str, object]] = [
        ("user_id", user.id),
        ("tg_id", user.tg_id),
        ("name", user.name),
        ("currency", user.currency),
        ("hourly_rate", _money(user.hourly_rate)),
        ("role", user.role),
        ("backup_date", today.isoformat()),
    ]
    for row_idx, (label, value) in enumerate(rows, 1):
        ws.cell(row=row_idx, column=1, value=label).font = bold
        ws.cell(row=row_idx, column=2, value=value)
    _set_widths(ws, (18, 24))


def _fill_day_entries(ws, entries: list[DayEntry]) -> None:  # noqa: ANN001
    _write_header(ws, ("id", "day", "hours", "site_id", "note", "created_at"))
    for row_idx, e in enumerate(entries, 2):
        ws.cell(row=row_idx, column=1, value=e.id)
        c = ws.cell(row=row_idx, column=2, value=e.day)
        c.number_format = _DATE_FMT
        c = ws.cell(row=row_idx, column=3, value=float(e.hours))
        c.number_format = _MONEY_FMT
        ws.cell(row=row_idx, column=4, value=e.site_id)
        ws.cell(row=row_idx, column=5, value=e.note)
        ws.cell(
            row=row_idx, column=6,
            value=e.created_at.isoformat() if e.created_at else None,
        )
    _set_widths(ws, (8, 12, 10, 10, 40, 26))


def _fill_advances(ws, advances: list[Advance]) -> None:  # noqa: ANN001
    _write_header(
        ws,
        ("id", "day", "period_year", "period_month", "amount", "note", "created_at"),
    )
    for row_idx, a in enumerate(advances, 2):
        ws.cell(row=row_idx, column=1, value=a.id)
        c = ws.cell(row=row_idx, column=2, value=a.day)
        c.number_format = _DATE_FMT
        ws.cell(row=row_idx, column=3, value=a.period_year)
        ws.cell(row=row_idx, column=4, value=a.period_month)
        c = ws.cell(row=row_idx, column=5, value=float(a.amount))
        c.number_format = _MONEY_FMT
        ws.cell(row=row_idx, column=6, value=a.note)
        ws.cell(
            row=row_idx, column=7,
            value=a.created_at.isoformat() if a.created_at else None,
        )
    _set_widths(ws, (8, 12, 12, 12, 12, 40, 26))


def _fill_payments(ws, payments: list[SalaryPayment]) -> None:  # noqa: ANN001
    _write_header(
        ws,
        (
            "id", "paid_on", "period_year", "period_month",
            "amount", "note", "created_at",
        ),
    )
    for row_idx, p in enumerate(payments, 2):
        ws.cell(row=row_idx, column=1, value=p.id)
        c = ws.cell(row=row_idx, column=2, value=p.paid_on)
        c.number_format = _DATE_FMT
        ws.cell(row=row_idx, column=3, value=p.period_year)
        ws.cell(row=row_idx, column=4, value=p.period_month)
        c = ws.cell(row=row_idx, column=5, value=float(p.amount))
        c.number_format = _MONEY_FMT
        ws.cell(row=row_idx, column=6, value=p.note)
        ws.cell(
            row=row_idx, column=7,
            value=p.created_at.isoformat() if p.created_at else None,
        )
    _set_widths(ws, (8, 12, 12, 12, 12, 40, 26))


def build_backup_xlsx(
    user: User,
    day_entries: list[DayEntry],
    advances: list[Advance],
    payments: list[SalaryPayment],
    today: date,
) -> BytesIO:
    """Build a 4-sheet workbook: profile + day_entries + advances + payments."""
    wb = Workbook()
    # First sheet is created by openpyxl; rename and use it as Profile.
    ws_profile = wb.active
    assert ws_profile is not None
    ws_profile.title = "Профиль"
    _fill_profile(ws_profile, user, today)

    ws_days = wb.create_sheet("Дни")
    _fill_day_entries(ws_days, day_entries)

    ws_adv = wb.create_sheet("Авансы")
    _fill_advances(ws_adv, advances)

    ws_pay = wb.create_sheet("Выплаты")
    _fill_payments(ws_pay, payments)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def backup_filename(user: User, today: date | datetime) -> str:
    d = today.date() if isinstance(today, datetime) else today
    return f"wh1_backup_{user.id}_{d.isoformat()}.xlsx"
