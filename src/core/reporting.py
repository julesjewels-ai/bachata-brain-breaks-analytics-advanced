"""
Reporting module for generating Excel reports.
Handles styling and formatting logic for Excel output.
"""
from typing import Dict, Optional
import pandas as pd
import logging
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field, ValidationError, field_validator
import re

from src.core.charting import ChartBuilder, ChartDataLocation

# Configure logging
logger = logging.getLogger(__name__)

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


class ExcelReportGenerator:
    """Generates styled Excel reports for analytics data."""

    HEADER_FONT = Font(bold=True, color="FFFFFF")
    HEADER_FILL = PatternFill(start_color="4F81BD", fill_type="solid")

    def __init__(self, chart_builder: Optional[ChartBuilder] = None):
        """
        Initialize with optional chart builder for dependency injection.
        """
        self.chart_builder = chart_builder or ChartBuilder()

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

    def _add_charts_if_possible(self, ws, df: pd.DataFrame, sheet_name: str):
        """Checks for compatible data and adds charts using ChartBuilder."""
        # Check if we have necessary columns
        if 'views' not in df.columns or 'title' not in df.columns:
            return

        try:
            # Find column indices (1-based for openpyxl)
            # df.columns is 0-based.
            views_col_idx = df.columns.get_loc('views') + 1
            title_col_idx = df.columns.get_loc('title') + 1

            # Data starts at row 2 (header is row 1)
            # Max row is number of records + 1
            max_row = len(df) + 1

            if len(df) > 0:
                location = ChartDataLocation(
                    min_col=views_col_idx,
                    min_row=2,
                    max_col=views_col_idx,
                    max_row=max_row,
                    categories_col=title_col_idx
                )

                chart_title = f"Views Analysis - {sheet_name.replace(' Anomalies', '')}"
                self.chart_builder.add_views_bar_chart(ws, location, chart_title)
        except Exception as e:
            logger.warning(f"Could not add chart to {sheet_name}: {e}")

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
                    sheet_name = f"{v_type} Anomalies"
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    ws = writer.sheets[sheet_name]
                    self._apply_header_style(ws)
                    self._apply_number_formats(ws)
                    self._adjust_column_widths(ws)

                    # Add Chart
                    self._add_charts_if_possible(ws, df, sheet_name)

            # 2. Strategy Sheet
            pd.DataFrame({'Gemini Analysis': [strategy]}).to_excel(
                writer, sheet_name="Strategy", index=False
            )
            ws_strat = writer.sheets["Strategy"]
            self._apply_header_style(ws_strat)
            ws_strat.column_dimensions['A'].width = 100
            align = ws_strat['A2'].alignment
            ws_strat['A2'].alignment = align.copy(wrap_text=True)
