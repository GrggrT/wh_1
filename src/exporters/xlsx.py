"""XLSX timesheet exporter."""

from datetime import date, time
from decimal import Decimal
from io import BytesIO
from zoneinfo import ZoneInfo

from openpyxl import Workbook
from openpyxl.styles import Font

from src.core.models import Crew, Shift, Site, User
from src.services.reports import compute_hours, split_shift_at_midnight


class ShiftRow:
    """Represents one row in the exported timesheet (after midnight splits)."""

    def __init__(
        self,
        shift_date: date,
        site_name: str,
        start_time: time,
        end_time: time,
        hours: Decimal,
        rate: Decimal | None,
        note: str | None,
    ) -> None:
        self.shift_date = shift_date
        self.site_name = site_name
        self.start_time = start_time
        self.end_time = end_time
        self.hours = hours
        self.rate = rate
        self.amount = hours * rate if rate else None
        self.note = note


def build_shift_rows(
    shifts: list[Shift],
    sites: dict[int, Site],
    user: User,
    tz: ZoneInfo,
) -> list[ShiftRow]:
    """Build export rows, splitting shifts at midnight."""
    rows: list[ShiftRow] = []

    for shift in shifts:
        if shift.end_at is None:
            continue

        site = sites.get(shift.site_id) if shift.site_id else None
        site_name = site.name if site else ""

        rate: Decimal | None = None
        if site and site.hourly_rate is not None:
            rate = site.hourly_rate
        elif user.hourly_rate is not None:
            rate = user.hourly_rate

        segments = split_shift_at_midnight(shift.start_at, shift.end_at, tz)
        for seg_start, seg_end in segments:
            hours = compute_hours(seg_start, seg_end)
            rows.append(
                ShiftRow(
                    shift_date=seg_start.date(),
                    site_name=site_name,
                    start_time=seg_start.timetz(),
                    end_time=seg_end.timetz(),
                    hours=hours.quantize(Decimal("0.01")),
                    rate=rate,
                    note=shift.note,
                )
            )

    return rows


def export_xlsx(
    shifts: list[Shift],
    sites: dict[int, Site],
    user: User,
    tz: ZoneInfo,
    period: str,
) -> BytesIO:
    """Generate XLSX workbook and return as BytesIO."""
    rows = build_shift_rows(shifts, sites, user, tz)
    wb = Workbook()

    # Sheet 1 - Shifts
    ws = wb.active
    assert ws is not None
    ws.title = "Shifts"

    headers = ["Date", "Site", "Start", "End", "Hours", "Rate (zl)", "Amount (zl)", "Note"]
    bold = Font(bold=True)
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = bold

    for row_idx, row in enumerate(rows, 2):
        ws.cell(row=row_idx, column=1, value=row.shift_date.isoformat())
        ws.cell(row=row_idx, column=2, value=row.site_name)
        ws.cell(row=row_idx, column=3, value=row.start_time.strftime("%H:%M"))
        ws.cell(row=row_idx, column=4, value=row.end_time.strftime("%H:%M"))

        hours_cell = ws.cell(row=row_idx, column=5, value=float(row.hours))
        hours_cell.number_format = "0.00"

        if row.rate is not None:
            rate_cell = ws.cell(row=row_idx, column=6, value=float(row.rate))
            rate_cell.number_format = "0.00"

        if row.amount is not None:
            amount_cell = ws.cell(row=row_idx, column=7, value=float(row.amount))
            amount_cell.number_format = "0.00"

        ws.cell(row=row_idx, column=8, value=row.note or "")

    # Sheet 2 - Summary
    ws_sum = wb.create_sheet("Summary")

    # Block 1: Hours per site
    ws_sum.cell(row=1, column=1, value="Hours per site").font = bold
    site_hours: dict[str, Decimal] = {}
    for row in rows:
        site_hours[row.site_name] = site_hours.get(row.site_name, Decimal(0)) + row.hours

    sum_row = 2
    for site_name, hours in sorted(site_hours.items()):
        ws_sum.cell(row=sum_row, column=1, value=site_name)
        c = ws_sum.cell(row=sum_row, column=2, value=float(hours))
        c.number_format = "0.00"
        sum_row += 1

    # Block 2: Hours per work_type
    sum_row += 1
    ws_sum.cell(row=sum_row, column=1, value="Hours per work type").font = bold
    sum_row += 1
    type_hours: dict[str, Decimal] = {}
    for shift in shifts:
        if shift.end_at is None:
            continue
        wt = shift.work_type or "(not specified)"
        h = compute_hours(shift.start_at, shift.end_at)
        type_hours[wt] = type_hours.get(wt, Decimal(0)) + h

    for wt, hours in sorted(type_hours.items()):
        ws_sum.cell(row=sum_row, column=1, value=wt)
        c = ws_sum.cell(row=sum_row, column=2, value=float(hours.quantize(Decimal("0.01"))))
        c.number_format = "0.00"
        sum_row += 1

    # Block 3: Grand totals
    sum_row += 1
    ws_sum.cell(row=sum_row, column=1, value="Grand total").font = bold
    sum_row += 1
    grand_hours = sum(r.hours for r in rows)
    grand_amount = sum(r.amount for r in rows if r.amount is not None)

    ws_sum.cell(row=sum_row, column=1, value="Total hours")
    c = ws_sum.cell(row=sum_row, column=2, value=float(grand_hours))
    c.number_format = "0.00"
    sum_row += 1

    ws_sum.cell(row=sum_row, column=1, value="Total amount (zl)")
    c = ws_sum.cell(row=sum_row, column=2, value=float(grand_amount))
    c.number_format = "0.00"

    # Save to buffer
    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


def export_crew_xlsx(
    crew: Crew,
    members: list[User],
    shifts_by_user: dict[int, list[Shift]],
    sites: dict[int, Site],
    tz: ZoneInfo,
    period: str,
) -> BytesIO:
    """Generate a crew-wide workbook: one sheet per member + summary."""
    wb = Workbook()
    bold = Font(bold=True)

    # Summary sheet first
    ws_sum = wb.active
    assert ws_sum is not None
    ws_sum.title = "Crew summary"
    ws_sum.cell(row=1, column=1, value=f"Crew: {crew.name}").font = bold
    ws_sum.cell(row=1, column=2, value=f"Period: {period}")
    ws_sum.cell(row=3, column=1, value="Member").font = bold
    ws_sum.cell(row=3, column=2, value="Hours").font = bold
    ws_sum.cell(row=3, column=3, value="Amount (zl)").font = bold
    ws_sum.cell(row=3, column=4, value="Shifts").font = bold

    summary_row = 4
    grand_hours = Decimal(0)
    grand_amount = Decimal(0)
    for member in members:
        member_shifts = shifts_by_user.get(member.id, [])
        rows = build_shift_rows(member_shifts, sites, member, tz)
        member_hours = sum((r.hours for r in rows), Decimal(0))
        member_amount = sum(
            (r.amount for r in rows if r.amount is not None), Decimal(0),
        )
        ws_sum.cell(row=summary_row, column=1, value=member.name)
        c = ws_sum.cell(row=summary_row, column=2, value=float(member_hours))
        c.number_format = "0.00"
        c = ws_sum.cell(row=summary_row, column=3, value=float(member_amount))
        c.number_format = "0.00"
        ws_sum.cell(
            row=summary_row, column=4,
            value=len([s for s in member_shifts if s.end_at is not None]),
        )
        summary_row += 1
        grand_hours += member_hours
        grand_amount += member_amount

        # Per-member sheet
        sheet_name = (member.name or f"user_{member.id}")[:31]
        ws = wb.create_sheet(sheet_name)
        headers = ["Date", "Site", "Start", "End", "Hours", "Rate (zl)", "Amount (zl)", "Note"]
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.font = bold
        for row_idx, row in enumerate(rows, 2):
            ws.cell(row=row_idx, column=1, value=row.shift_date.isoformat())
            ws.cell(row=row_idx, column=2, value=row.site_name)
            ws.cell(row=row_idx, column=3, value=row.start_time.strftime("%H:%M"))
            ws.cell(row=row_idx, column=4, value=row.end_time.strftime("%H:%M"))
            hc = ws.cell(row=row_idx, column=5, value=float(row.hours))
            hc.number_format = "0.00"
            if row.rate is not None:
                rc = ws.cell(row=row_idx, column=6, value=float(row.rate))
                rc.number_format = "0.00"
            if row.amount is not None:
                ac = ws.cell(row=row_idx, column=7, value=float(row.amount))
                ac.number_format = "0.00"
            ws.cell(row=row_idx, column=8, value=row.note or "")

    summary_row += 1
    ws_sum.cell(row=summary_row, column=1, value="Grand total").font = bold
    c = ws_sum.cell(row=summary_row, column=2, value=float(grand_hours))
    c.number_format = "0.00"
    c = ws_sum.cell(row=summary_row, column=3, value=float(grand_amount))
    c.number_format = "0.00"

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
