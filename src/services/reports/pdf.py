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


def _ensure_fonts() -> None:
    """Register the bundled TTFs with reportlab once per process."""
    global _FONTS_REGISTERED  # noqa: PLW0603
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont(_FONT_REGULAR, str(_FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(_FONT_DIR / "DejaVuSans-Bold.ttf")))
    _FONTS_REGISTERED = True


def _fmt_money(value: Decimal | None) -> str:
    return "—" if value is None else f"{value:.2f}"


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
        fontSize=16,
        leading=20,
    )
    sub_style = ParagraphStyle(
        "SubRu",
        parent=styles["Normal"],
        fontName=_FONT_REGULAR,
        fontSize=10,
        leading=12,
        textColor=colors.HexColor("#555555"),
    )

    story: list[object] = [
        Paragraph(f"Отчёт за последние {data.months} мес.", title_style),
        Paragraph(f"Сотрудник: {user.name or '—'}  ·  Валюта: {cur}", sub_style),
        Spacer(1, 10),
    ]

    headers = [
        "Период", "Часы",
        f"Начислено ({cur})", f"Получено ({cur})", f"Остаток ({cur})",
        "Статус",
    ]
    table_rows: list[list[str]] = [headers]

    for led in data.ledgers:
        period = f"{_RU_MONTHS[led.month - 1]} {led.year}"
        table_rows.append([
            period,
            f"{led.hours:.2f}",
            _fmt_money(led.earnings),
            _fmt_money(led.received_total),
            _fmt_money(led.remaining),
            _STATUS_TAGS.get(led.status, led.status),
        ])

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
        colWidths=[110, 60, 110, 110, 110, 110],
        repeatRows=1,
    )
    style = TableStyle([
        ("FONT", (0, 0), (-1, -1), _FONT_REGULAR, 10),
        ("FONT", (0, 0), (-1, 0), _FONT_BOLD, 10),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EFEFEF")),
        ("ALIGN", (1, 1), (4, -1), "RIGHT"),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BBBBBB")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ])

    totals_row = len(table_rows) - (
        2 if data.total_overpaid > 0 else 1
    )
    style.add("FONT", (0, totals_row), (-1, totals_row), _FONT_BOLD, 10)
    style.add(
        "BACKGROUND", (0, totals_row), (-1, totals_row),
        colors.HexColor("#FAFAFA"),
    )
    if data.total_overpaid > 0:
        over_row = len(table_rows) - 1
        style.add("FONT", (0, over_row), (-1, over_row), _FONT_BOLD, 10)

    table.setStyle(style)
    story.append(table)

    doc.build(story)
    buf.seek(0)
    return buf


def pdf_filename(months: int) -> str:
    return f"report_{months}m.pdf"
