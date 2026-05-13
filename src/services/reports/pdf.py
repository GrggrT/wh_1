"""Phase 6.11c: PDF renderer for ``ReportData``.

Uses reportlab's platypus tables for an A4 landscape one-pager. We ship
``DejaVuSans`` (regular + bold) so Cyrillic + emoji-status tags render
correctly without depending on system font availability on Railway.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src.core.models import User
from src.services.reports.service import ReportData

_FONT_DIR = Path(__file__).parent / "assets"
_FONT_REGULAR = "DejaVuSans"
_FONT_BOLD = "DejaVuSans-Bold"
_FONTS_REGISTERED = False

_RU_MONTHS: tuple[str, ...] = (
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
)

_STATUS_TAGS: dict[str, str] = {
    "settled": "закрыт",
    "pending": "ожидает",
    "partial": "частично",
    "overpaid": "переплата",
    "unpriced": "без ставки",
}

_STATUS_FILLS: dict[str, str] = {
    "settled": "#D1FAE5",   # emerald-100
    "pending": "#FEE2E2",   # red-100
    "partial": "#FEF3C7",   # amber-100
    "overpaid": "#DBEAFE",  # blue-100
    "unpriced": "#F3F4F6",  # gray-100
}

_BRAND_NAVY = "#1F2937"
_BRAND_MUTED = "#6B7280"
_BRAND_GRID = "#E5E7EB"
_STRIPE_ROW = "#F9FAFB"
_TOTALS_ROW = "#F3F4F6"


def _ensure_fonts() -> None:
    """Register the bundled TTFs with reportlab once per process."""
    global _FONTS_REGISTERED  # noqa: PLW0603
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
    _FONTS_REGISTERED = True


def _fmt_money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    # Thousand-space separator, two decimals.
    return f"{value:,.2f}".replace(",", " ")


def build_report_pdf(data: ReportData, user: User) -> BytesIO:
    """Render ``data`` into an in-memory ``.pdf`` buffer (A4 landscape)."""
    _ensure_fonts()
    cur = user.currency

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24,
        title=f"Отчёт за {data.months} мес.",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleRu",
        parent=styles["Title"],
        fontName=_FONT_BOLD,
        fontSize=18,
        leading=22,
        textColor=colors.HexColor(_BRAND_NAVY),
        alignment=0,  # left
    )
    sub_style = ParagraphStyle(
        "SubRu",
        parent=styles["Normal"],
        fontName=_FONT_REGULAR,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor(_BRAND_MUTED),
    )

    story: list[object] = [
        Paragraph(f"Отчёт за последние {data.months} мес.", title_style),
        Paragraph(f"Сотрудник: {user.name or '—'}  ·  Валюта: {cur}", sub_style),
        Spacer(1, 14),
    ]

    headers = [
        "Период", "Часы",
        f"Начислено ({cur})", f"Получено ({cur})", f"Остаток ({cur})",
        "Статус",
    ]
    table_rows: list[list[str]] = [headers]

    status_rows: list[tuple[int, str]] = []
    for idx, led in enumerate(data.ledgers, start=1):
        period = f"{_RU_MONTHS[led.month - 1]} {led.year}"
        table_rows.append([
            period,
            f"{led.hours:.2f}",
            _fmt_money(led.earnings),
            _fmt_money(led.received_total),
            _fmt_money(led.remaining),
            _STATUS_TAGS.get(led.status, led.status),
        ])
        status_rows.append((idx, led.status))

    table_rows.append([
        "Итого",
        f"{data.total_hours:.2f}",
        _fmt_money(data.total_earnings),
        _fmt_money(data.total_received),
        _fmt_money(data.total_owed),
        f"долг ({cur})",
    ])

    if data.total_overpaid > 0:
        table_rows.append([
            "Переплата",
            "",
            "",
            "",
            _fmt_money(data.total_overpaid),
            f"переплата ({cur})",
        ])

    table = Table(
        table_rows,
        colWidths=[110, 60, 110, 110, 110, 120],
        repeatRows=1,
    )
    style = TableStyle([
        ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 10),
        ("FONT", (0, 0), (-1, 0), _FONT_BOLD, 11),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_BRAND_NAVY)),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.HexColor(_BRAND_NAVY)),
        ("ALIGN", (1, 1), (4, -1), "RIGHT"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (5, 1), (5, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0, colors.HexColor(_BRAND_NAVY)),
        ("LINEABOVE", (0, 1), (-1, -1), 0.25, colors.HexColor(_BRAND_GRID)),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor(_BRAND_GRID)),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ])

    # Alternating stripes for body rows (skip the header, totals, overpaid).
    last_body_row = len(data.ledgers)  # rows 1..N are body
    for r in range(1, last_body_row + 1):
        if r % 2 == 0:
            style.add(
                "BACKGROUND", (0, r), (-1, r), colors.HexColor(_STRIPE_ROW),
            )

    # Status-column color cues for body rows.
    for r, status in status_rows:
        fill = _STATUS_FILLS.get(status)
        if fill is not None:
            style.add("BACKGROUND", (5, r), (5, r), colors.HexColor(fill))

    totals_row = len(table_rows) - (
        2 if data.total_overpaid > 0 else 1
    )
    style.add("FONT", (0, totals_row), (-1, totals_row), _FONT_BOLD, 10)
    style.add(
        "BACKGROUND", (0, totals_row), (-1, totals_row),
        colors.HexColor(_TOTALS_ROW),
    )
    style.add(
        "LINEABOVE", (0, totals_row), (-1, totals_row),
        0.75, colors.HexColor(_BRAND_NAVY),
    )
    if data.total_overpaid > 0:
        over_row = len(table_rows) - 1
        style.add("FONT", (0, over_row), (-1, over_row), _FONT_BOLD, 10)
        style.add(
            "BACKGROUND", (0, over_row), (-1, over_row),
            colors.HexColor(_TOTALS_ROW),
        )

    table.setStyle(style)
    story.append(table)

    doc.build(story)
    buf.seek(0)
    return buf


def pdf_filename(months: int) -> str:
    return f"report_{months}m.pdf"
