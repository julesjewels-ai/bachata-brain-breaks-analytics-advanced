"""
Reporting module for generating Excel reports.
Handles styling and formatting logic for Excel output.
"""
from typing import Dict, Any
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field, ValidationError, field_validator
import re


class ReportConfig(BaseModel):
    """Configuration for report generation validation."""
    filepath: str = Field(..., description="Path to save the Excel report")

    @field_validator('filepath')
    @classmethod
    def validate_filepath(cls, v: str) -> str:
        if not v.endswith('.xlsx'):
            raise ValueError("File must be an Excel (.xlsx) file")
        if '..' in v:
            raise ValueError("Path traversal detected")
        if not re.match(r'^[\w\-. /]+$', v):
            raise ValueError("File path contains invalid characters")
        return v


class ExcelSanitizer(BaseModel):
    """
    Sanitizes data for Excel to prevent formula injection.
    Follows Single Responsibility Principle.
    """

    @staticmethod
    def sanitize_value(value: Any) -> Any:
        """
        Sanitizes a single value to prevent CSV/Formula injection.
        Prefixes strings starting with =, @, +, or - with a single quote.
        """
        if isinstance(value, str):
            if value.startswith(('=', '@', '+', '-')):
                return f"'{value}"
        return value

    @staticmethod
    def sanitize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Applies sanitization to all string columns in a DataFrame.
        """
        return df.map(ExcelSanitizer.sanitize_value)


class ExcelReportGenerator:
    """Generates styled Excel reports for analytics data."""

    HEADER_FONT = Font(bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="4F81BD", fill_type="solid")

    @staticmethod
    def _adjust_column_widths(ws):
        """Auto-adjusts column widths based on content length."""
        for col in ws.columns:
            # Convert to string safely to check length
            max_length = max((len(str(cell.value) if cell.value is not None else "") for cell in col), default=0)
            ws.column_dimensions[get_column_letter(col[0].column)].width = max_length + 2

    @staticmethod
    def _apply_header_style(ws):
        """Applies standard header styling and freezes panes."""
        for cell in ws[1]:
            cell.font = ExcelReportGenerator.HEADER_FONT
            cell.fill = ExcelReportGenerator.HEADER_FILL
        ws.freeze_panes = 'A2'

    @staticmethod
    def _apply_number_formats(ws):
        """Applies number formatting to specific columns."""
        # Map column headers to their respective formats
        format_map = {
            'views': '#,##0',
            'retention_avg_pct': '0.00"%"'
        }

        # Find column indices for headers
        headers = {cell.value: cell.column for cell in ws[1]}

        for header, fmt in format_map.items():
            if header in headers:
                col_idx = headers[header]
                # Apply format to all cells in the column (skipping header)
                for row in range(2, ws.max_row + 1):
                    ws.cell(row=row, column=col_idx).number_format = fmt

    def generate_excel(self,
                       anomalies: Dict[str, pd.DataFrame],
                       strategy: str,
                       filepath: str):
        """Creates an Excel report with anomalies and strategy analysis."""
        try:
            config = ReportConfig(filepath=filepath)
            safe_path = config.filepath
        except ValidationError as e:
            raise ValueError(f"Security validation failed: {e}")

        with pd.ExcelWriter(safe_path, engine='openpyxl') as writer:
            # 1. Anomalies Sheets
            for v_type, df in anomalies.items():
                if not df.empty:
                    # Sanitize data before writing
                    safe_df = ExcelSanitizer.sanitize_dataframe(df)
                    sheet_name = f"{v_type} Anomalies"
                    safe_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    ws = writer.sheets[sheet_name]
                    self._apply_header_style(ws)
                    self._apply_number_formats(ws)
                    self._adjust_column_widths(ws)

            # 2. Strategy Sheet
            # Sanitize strategy text as well
            safe_strategy = ExcelSanitizer.sanitize_value(strategy)
            pd.DataFrame({'Gemini Analysis': [safe_strategy]}).to_excel(
                writer, sheet_name="Strategy", index=False
            )
            ws_strat = writer.sheets["Strategy"]
            self._apply_header_style(ws_strat)
            ws_strat.column_dimensions['A'].width = 100

            # Use new Alignment object to avoid deprecation warning
            current_align = ws_strat['A2'].alignment
            ws_strat['A2'].alignment = Alignment(
                horizontal=current_align.horizontal,
                vertical=current_align.vertical,
                text_rotation=current_align.text_rotation,
                wrap_text=True,
                shrink_to_fit=current_align.shrink_to_fit,
                indent=current_align.indent
            )
