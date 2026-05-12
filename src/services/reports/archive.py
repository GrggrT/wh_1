"""Phase 7.8: ``/export-archive`` — bundle XLSX + PDF + PNG into one ZIP.

A single download containing all three report formats for the same
``months`` window. Useful when forwarding a full report to an
accountant without juggling three messages.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

from src.core.models import User
from src.services.reports.pdf import build_report_pdf, pdf_filename
from src.services.reports.png import build_report_png, png_filename
from src.services.reports.service import ReportData
from src.services.reports.xlsx import build_report_xlsx, xlsx_filename


def build_report_archive(data: ReportData, user: User, months: int) -> BytesIO:
    """Return an in-memory ZIP containing the XLSX, PDF and PNG report."""
    xlsx_buf = build_report_xlsx(data, user)
    pdf_buf = build_report_pdf(data, user)
    png_buf = build_report_png(data, user)

    out = BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(xlsx_filename(months), xlsx_buf.getvalue())
        zf.writestr(pdf_filename(months), pdf_buf.getvalue())
        zf.writestr(png_filename(months), png_buf.getvalue())
    out.seek(0)
    return out


def archive_filename(months: int) -> str:
    return f"report_{months}m.zip"
