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
from matplotlib.ticker import MaxNLocator  # noqa: E402

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

    fig, ax = plt.subplots(figsize=(max(6.0, len(ordered) * 0.9), 4.2), dpi=140)

    x_positions = list(range(len(ordered)))
    bar_width = 0.38
    earned_bars = ax.bar(
        [x - bar_width / 2 for x in x_positions],
        earned,
        bar_width,
        label="Начислено",
        color="#3D6EB5",
    )
    received_bars = ax.bar(
        [x + bar_width / 2 for x in x_positions],
        received,
        bar_width,
        label="Получено",
        color="#5CB85C",
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(labels)
    ax.set_ylabel(cur)
    ax.set_title(f"Отчёт за последние {data.months} мес.", fontweight="bold")
    ax.yaxis.set_major_locator(MaxNLocator(integer=False, prune="lower"))
    ax.grid(axis="y", linestyle=":", linewidth=0.6, alpha=0.6)
    ax.set_axisbelow(True)
    ax.legend(loc="upper left", frameon=False)

    # Value labels above each bar (skip zeros to reduce clutter).
    for bars, values in ((earned_bars, earned), (received_bars, received)):
        for rect, val in zip(bars, values, strict=True):
            if val <= 0:
                continue
            ax.annotate(
                f"{val:.0f}",
                xy=(rect.get_x() + rect.get_width() / 2, val),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    footer = _footer_text(data, cur)
    fig.text(
        0.5, 0.01, footer, ha="center", va="bottom",
        fontsize=10, fontweight="bold",
    )

    fig.tight_layout(rect=(0, 0.04, 1, 1))

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=140)
    plt.close(fig)
    buf.seek(0)
    return buf


def _footer_text(data: ReportData, currency: str) -> str:
    parts: list[str] = [f"Часы: {data.total_hours:.0f}"]
    if data.total_earnings is not None:
        parts.append(f"начислено {data.total_earnings:.2f} {currency}")
    parts.append(f"получено {data.total_received:.2f} {currency}")
    if data.total_owed > Decimal(0):
        parts.append(f"долг {data.total_owed:.2f} {currency}")
    elif data.total_overpaid > Decimal(0):
        parts.append(f"переплата {data.total_overpaid:.2f} {currency}")
    return "  ·  ".join(parts)


def png_filename(months: int) -> str:
    return f"report_{months}m.png"
