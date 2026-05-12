"""Phase 6.11e: NL phrase parser for accounting intents.

Maps free-text Russian phrases to one of four intents: ``report`` (rolling
multi-month), ``period`` (single month), ``cash`` (cashflow for a month),
``owed`` (debt summary). Pure regex/keyword matching — no LLM. The caller
must pass the user's "today" so relative month references resolve
deterministically (e.g. «декабрь» said in May 2026 → December 2025).
"""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import date

# Month-name stems → 1..12. Russian month forms (nominative, genitive,
# prepositional) share these prefixes.
_MONTH_PATTERNS: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"\bянвар\w*", re.IGNORECASE), 1),
    (re.compile(r"\bфеврал\w*", re.IGNORECASE), 2),
    (re.compile(r"\bмарт\w*", re.IGNORECASE), 3),
    (re.compile(r"\bапрел\w*", re.IGNORECASE), 4),
    (re.compile(r"\bма[йяе]\b", re.IGNORECASE), 5),
    (re.compile(r"\bиюн\w*", re.IGNORECASE), 6),
    (re.compile(r"\bиюл\w*", re.IGNORECASE), 7),
    (re.compile(r"\bавгуст\w*", re.IGNORECASE), 8),
    (re.compile(r"\bсентябр\w*", re.IGNORECASE), 9),
    (re.compile(r"\bоктябр\w*", re.IGNORECASE), 10),
    (re.compile(r"\bноябр\w*", re.IGNORECASE), 11),
    (re.compile(r"\bдекабр\w*", re.IGNORECASE), 12),
)

_YEAR_RE = re.compile(r"\b(20\d{2})\b")

# Catches "за 3 месяца", "12 мес", "за N месяцев" etc.
_N_MONTHS_RE = re.compile(
    r"\b(\d{1,2})\s*(?:мес(?:\.|яц(?:а|ев)?)?|months?)\b",
    re.IGNORECASE,
)

_KW_OWED = ("долг", "должн", "не выплачен", "остаток")
_KW_CASH = ("касс", "движен", "поток")
_KW_REPORT = ("отчёт", "отчет", "сводк", "report")
_KW_PERIOD_HINT = ("период", "за месяц")
_KW_FORECAST = ("прогноз", "до конца месяц", "сколько заработ", "forecast")

# Two ISO dates anywhere in text, separated by whitespace or a dash/«по».
_ISO_PAIR_RE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*(?:[-–—]|по|до|–)?\s*(\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)

# "1-15 мая", "с 1 по 15 мая", "1 - 15 мая". Month-name resolved separately.
_DAY_RANGE_RE = re.compile(
    r"(?:с\s+)?(\d{1,2})\s*(?:[-–—]|по|до)\s*(\d{1,2})\b",
    re.IGNORECASE,
)


@dataclass
class NLIntent:
    """Result of parsing a free-text phrase."""

    kind: str  # "report" | "period" | "cash" | "owed" | "forecast" | "range"
    year: int | None = None
    month: int | None = None  # 1..12
    months: int | None = None  # rolling window for "report"
    start: date | None = None  # range intent
    end: date | None = None  # range intent


def _detect_month(text: str, today: date) -> tuple[int, int] | None:
    """Return ``(year, month)`` if ``text`` mentions a Russian month name."""
    found_month: int | None = None
    for pat, mnum in _MONTH_PATTERNS:
        if pat.search(text):
            found_month = mnum
            break
    if found_month is None:
        return None
    year_match = _YEAR_RE.search(text)
    if year_match:
        return int(year_match.group(1)), found_month
    # Disambiguate: if the named month is in the future this year, the user
    # almost certainly means last year's instance.
    year = today.year
    if found_month > today.month:
        year -= 1
    return year, found_month


def _detect_n_months(text: str) -> int | None:
    """Return the N from "за N месяцев" / "N мес" if present."""
    match = _N_MONTHS_RE.search(text)
    if match is None:
        return None
    try:
        n = int(match.group(1))
    except ValueError:
        return None
    return n if 1 <= n <= 24 else None


def _detect_range(text: str, today: date) -> tuple[date, date] | None:
    """Detect a date range. Tries ISO pair first, then DD-DD <month>."""
    iso = _ISO_PAIR_RE.search(text)
    if iso:
        try:
            start = date.fromisoformat(iso.group(1))
            end = date.fromisoformat(iso.group(2))
        except ValueError:
            return None
        if end < start:
            start, end = end, start
        return start, end
    day_match = _DAY_RANGE_RE.search(text)
    if day_match is None:
        return None
    ym = _detect_month(text, today)
    if ym is None:
        return None
    year, month = ym
    try:
        d1 = int(day_match.group(1))
        d2 = int(day_match.group(2))
    except ValueError:
        return None
    last_day = calendar.monthrange(year, month)[1]
    if not (1 <= d1 <= last_day) or not (1 <= d2 <= last_day):
        return None
    start = date(year, month, min(d1, d2))
    end = date(year, month, max(d1, d2))
    return start, end


def parse_intent(text: str, *, today: date) -> NLIntent | None:
    """Best-effort parse of ``text`` into an accounting intent.

    Returns ``None`` when nothing actionable is detected so the caller
    can stay silent and let the message fall through.
    """
    if not text:
        return None
    s = text.strip().lower()
    if not s or s.startswith("/"):
        return None

    rng = _detect_range(s, today)
    if rng is not None:
        return NLIntent(kind="range", start=rng[0], end=rng[1])

    ym = _detect_month(s, today)
    n_months = _detect_n_months(s)

    if any(kw in s for kw in _KW_FORECAST):
        return NLIntent(kind="forecast")

    if any(kw in s for kw in _KW_OWED):
        return NLIntent(kind="owed")

    if any(kw in s for kw in _KW_CASH):
        year = ym[0] if ym else None
        month = ym[1] if ym else None
        return NLIntent(kind="cash", year=year, month=month)

    # "отчёт за май" → single-month deep-dive (period); "отчёт за 6 мес"
    # → multi-month rolling.
    if any(kw in s for kw in _KW_REPORT):
        if ym is not None:
            return NLIntent(kind="period", year=ym[0], month=ym[1])
        return NLIntent(kind="report", months=n_months)

    if ym is not None:
        return NLIntent(kind="period", year=ym[0], month=ym[1])

    if any(kw in s for kw in _KW_PERIOD_HINT):
        return NLIntent(kind="period")

    if n_months is not None:
        return NLIntent(kind="report", months=n_months)

    return None
