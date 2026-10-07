"""Excel export for the reconciliation result."""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .engine import ReconciliationResult


AMBER = "FFB800"
BLACK = "0B0C0A"
OFF_WHITE = "F2F2EF"
GREEN = "00E676"
RED = "FF3B30"


def _presentation_frame(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    drop_columns = [
        column
        for column in ("normalised_description", "normalised_reference")
        if column in output.columns
    ]
    if drop_columns:
        output = output.drop(columns=drop_columns)
    return output


def _style_sheet(sheet) -> None:
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor=BLACK)
        cell.font = Font(color=AMBER, bold=True)
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 24
    for column_cells in sheet.columns:
        letter = get_column_letter(column_cells[0].column)
        width = max(len(str(cell.value or "")) for cell in column_cells[:250]) + 2
        sheet.column_dimensions[letter].width = min(max(width, 11), 42)
    for row in sheet.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, float):
                cell.number_format = '#,##0.00;[Red]-#,##0.00'


def build_excel_report(result: ReconciliationResult) -> bytes:
    """Return a formatted, review-ready XLSX workbook as bytes."""

    status = "RECONCILED" if result.is_reconciled else "OPEN"
    summary = pd.DataFrame(
        [
            ("Status", status),
            ("Bank balance / movement", result.bank_balance),
            ("GL cash balance / movement", result.gl_balance),
            ("Bank-side adjustments", result.bank_adjustments),
            ("Book-side adjustments", result.book_adjustments),
            ("Adjusted bank balance", result.adjusted_bank_balance),
            ("Adjusted book balance", result.adjusted_book_balance),
            ("Residual", result.residual),
            ("Matched pairs", len(result.matches)),
            ("Exceptions", len(result.exceptions)),
            ("Source-row match rate", result.match_rate),
        ],
        columns=["Control", "Value"],
    )

    exception_groups = {
        "Exceptions": result.exceptions,
        "Outstanding Checks": result.exceptions[
            result.exceptions.get("category", pd.Series(dtype=str)) == "Outstanding check"
        ],
        "Deposits in Transit": result.exceptions[
            result.exceptions.get("category", pd.Series(dtype=str)) == "Deposit in transit"
        ],
        "Suggested Entries": result.exceptions[
            result.exceptions.get("suggested_account", pd.Series(dtype=str)) != "No journal entry"
        ],
    }

    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        summary.to_excel(writer, sheet_name="Control Summary", index=False)
        _presentation_frame(result.matches).to_excel(writer, sheet_name="Matched", index=False)
        for sheet_name, frame in exception_groups.items():
            _presentation_frame(frame).to_excel(writer, sheet_name=sheet_name, index=False)
        _presentation_frame(result.bank).to_excel(writer, sheet_name="Bank Source", index=False)
        _presentation_frame(result.gl).to_excel(writer, sheet_name="GL Source", index=False)

        for sheet in writer.book.worksheets:
            _style_sheet(sheet)

        summary_sheet = writer.book["Control Summary"]
        status_cell = summary_sheet["B2"]
        status_cell.fill = PatternFill(
            "solid", fgColor=GREEN if result.is_reconciled else RED
        )
        status_cell.font = Font(color=BLACK, bold=True)
        summary_sheet["B12"].number_format = "0.0%"

    return buffer.getvalue()
