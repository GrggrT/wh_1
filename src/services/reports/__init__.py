"""Reports package.

Re-exports the legacy shift-report helpers (``shifts.py``) so existing
imports like ``from src.services.reports import compute_hours`` keep
working unchanged. Phase 6.11+ adds the period-summary ``ReportData``
builder (``service.py``) and its text renderer (``text.py``).
"""

from src.services.reports.shifts import (
    compute_hours,
    compute_period_earnings,
    compute_period_hours,
    get_shifts_for_period,
    get_shifts_for_users_in_period,
    get_site_for_shift,
    split_shift_at_midnight,
)

__all__ = [
    "compute_hours",
    "compute_period_earnings",
    "compute_period_hours",
    "get_shifts_for_period",
    "get_shifts_for_users_in_period",
    "get_site_for_shift",
    "split_shift_at_midnight",
]
