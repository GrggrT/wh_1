"""Phase 6.11d: PNG bar chart for ``ReportData``.

Renders a side-by-side bar chart — «начислено» vs «получено» per period —
plus a footer line showing total owed (or overpaid). Uses matplotlib with
the ``Agg`` backend so it works headlessly inside the bot worker.
"""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

import matplotlib

matplotlib.use("Agg")  # noqa: E402 — must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from src.core.models import User  # noqa: E402
from src.services.reports.service import ReportData  # noqa: E402

_FONT_DIR = __import__("pathlib").Path(__file__).parent / "assets"
_FONT_PATH = _FONT_DIR / "DejaVuSans.ttf"
_FONT_BOLD_PATH = _FONT_DIR / "DejaVuSans-Bold.ttf"
_FONTS_REGISTERED = False

_RU_MONTHS_SHORT: tuple[str, ...] = (
    "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
    "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек",
)


def _ensure_fonts() -> None:
    """Register the bundled DejaVuSans so Cyrillic labels render."""
    global _FONTS_REGISTERED  # noqa: PLW0603
    if _FONTS_REGISTERED:
        return
    font_manager.fontManager.addfont(str(_FONT_PATH))
    font_manager.fontManager.addfont(str(_FONT_BOLD_PATH))
    plt.rcParams["font.family"] = "DejaVu Sans"
    _FONTS_REGISTERED = True


def build_report_png(data: ReportData, user: User) -> BytesIO:
    """Render ``data`` into an in-memory ``.png`` buffer."""
    _ensure_fonts()
    cur = user.currency

    # Modern, accessible palette (Tailwind blue-600 + emerald-500).
    color_earned = "#2563EB"
    color_received = "#10B981"
    color_text = "#1F2937"
    color_muted = "#6B7280"
    color_grid = "#E5E7EB"

    # Oldest first on the X axis so the eye reads left-to-right.
    ordered = list(reversed(data.ledgers))
    labels = [
        f"{_RU_MONTHS_SHORT[lg.month - 1]} {lg.year % 100:02d}"
        for lg in ordered
    ]
    earned = [
        float(lg.earnings) if lg.earnings is not None else 0.0
        for lg in ordered
    ]
    received = [float(lg.received_total) for lg in ordered]

    fig, ax = plt.subplots(figsize=(max(6.4, len(ordered) * 0.95), 4.6), dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("#FAFAFA")

    x_positions = list(range(len(ordered)))
    bar_width = 0.38
    earned_bars = ax.bar(
        [x - bar_width / 2 for x in x_positions],
        earned,
        bar_width,
        label="Начислено",
        color=color_earned,
        edgecolor="white",
        linewidth=0.8,
    )
    received_bars = ax.bar(
        [x + bar_width / 2 for x in x_positions],
        received,
        bar_width,
        label="Получено",
        color=color_received,
        edgecolor="white",
        linewidth=0.8,
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels, color=color_text)
    ax.set_ylabel(cur, color=color_muted, fontsize=10)
    ax.set_title(
        f"Отчёт за последние {data.months} мес.",
        fontweight="bold", fontsize=14, color=color_text, pad=24,
    )
    subtitle = f"{user.name or '—'}  ·  валюта: {cur}"
    ax.text(
        0.0, 1.02, subtitle, transform=ax.transAxes,
        ha="left", va="bottom", fontsize=9, color=color_muted,
    )
    ax.yaxis.set_major_locator(MaxNLocator(integer=False, prune="lower"))
    ax.yaxis.set_major_formatter(
        FuncFormatter(lambda v, _p: _fmt_thousands(v)),
    )
    ax.tick_params(axis="both", colors=color_muted, length=0)
    ax.grid(axis="y", linestyle="-", linewidth=0.6, color=color_grid)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.spines["left"].set_color(color_grid)
    ax.spines["bottom"].set_color(color_grid)
    legend = ax.legend(
        loc="upper left", frameon=False, fontsize=9, labelcolor=color_text,
    )
    for txt in legend.get_texts():
        txt.set_color(color_text)

    # Value labels above each bar (skip zeros to reduce clutter).
    for bars, values in ((earned_bars, earned), (received_bars, received)):
        for rect, val in zip(bars, values, strict=True):
            if val <= 0:
                continue
            ax.annotate(
                _fmt_thousands(val),
                xy=(rect.get_x() + rect.get_width() / 2, val),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
                color=color_text,
            )

    footer = _footer_text(data, cur)
    footer_color = _footer_color(data, color_text)
    fig.text(
        0.5, 0.015, footer, ha="center", va="bottom",
        fontsize=10, fontweight="bold", color=footer_color,
    )

    fig.tight_layout(rect=(0, 0.05, 1, 0.96))

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf


def _fmt_thousands(value: float) -> str:
    if value == 0:
        return "0"
    sign = "-" if value < 0 else ""
    av = abs(value)
    if av >= 1000:
        return f"{sign}{av:,.0f}".replace(",", " ")
    if av >= 10:
        return f"{sign}{av:.0f}"
    return f"{sign}{av:.1f}"


def _footer_color(data: ReportData, default: str) -> str:
    if data.total_owed > Decimal(0):
        return "#DC2626"  # red-600 for outstanding debt
    if data.total_overpaid > Decimal(0):
        return "#10B981"  # emerald-500 for overpaid
    return default


def _footer_text(data: ReportData, currency: str) -> str:
    parts: list[str] = [f"Часы: {_fmt_thousands(float(data.total_hours))}"]
    if data.total_earnings is not None:
        parts.append(
            f"начислено {_fmt_thousands(float(data.total_earnings))} {currency}",
        )
    parts.append(
        f"получено {_fmt_thousands(float(data.total_received))} {currency}",
    )
    if data.total_owed > Decimal(0):
        parts.append(
            f"долг {_fmt_thousands(float(data.total_owed))} {currency}",
        )
    elif data.total_overpaid > Decimal(0):
        parts.append(
            f"переплата {_fmt_thousands(float(data.total_overpaid))} {currency}",
        )
    return "  ·  ".join(parts)


def png_filename(months: int) -> str:
    return f"report_{months}m.png"
