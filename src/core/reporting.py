"""
Reporting module for generating Excel reports.
Handles styling and formatting logic for Excel output.
"""
from typing import Dict
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from pydantic import BaseModel, Field, ValidationError, field_validator
import re

from src.core.charting import ChartBuilder, ChartConfig, ChartDataLocation


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

    # Mapping from DataFrame columns to Excel headers
    COLUMN_MAPPING = {
        'video_id': 'Video ID',
        'title': 'Video Title',
        'views': 'Views',
        'retention_avg_pct': 'Retention (%)',
        'type': 'Type',
        'publish_date': 'Publish Date'
    }

    @staticmethod
    def _adjust_column_widths(ws):
        """Auto-adjusts column widths based on content length with min/max constraints."""
        min_width = 10
        max_width = 50
        for col in ws.columns:
            # Calculate max length of data in column
            max_length = 0
            for cell in col:
                val = str(cell.value) if cell.value is not None else ""
                max_length = max(max_length, len(val))

            # Apply padding and clamp between min and max
            adjusted_width = max(min_width, min(max_length + 2, max_width))
            ws.column_dimensions[get_column_letter(col[0].column)].width = adjusted_width

    @staticmethod
    def _apply_header_style(ws):
        """Applies standard header styling (Bold, Centered, Blue) and freezes panes."""
        for cell in ws[1]:
            cell.font = ExcelReportGenerator.HEADER_FONT
            cell.fill = ExcelReportGenerator.HEADER_FILL
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.freeze_panes = 'A2'

    @staticmethod
    def _apply_number_formats(ws):
        """Applies number formatting to specific columns."""
        # Map column headers to their respective formats
        format_map = {
            'Views': '#,##0',
            'Retention (%)': '0.00"%"'
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
                    sheet_name = f"{v_type} Anomalies"
                    # Rename columns for better readability
                    display_df = df.rename(columns=self.COLUMN_MAPPING)
                    display_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    ws = writer.sheets[sheet_name]
                    self._apply_header_style(ws)
                    self._apply_number_formats(ws)
                    self._adjust_column_widths(ws)

                    # Add Chart
                    # Locate 'Views' column
                    headers = {cell.value: cell.column for cell in ws[1]}
                    if 'Views' in headers and 'Video Title' in headers:
                        views_col = headers['Views']
                        title_col = headers['Video Title']
                        max_row = ws.max_row
                        max_col = ws.max_column

                        # Only add chart if there is data
                        if max_row > 1:
                            chart_builder = ChartBuilder(ws)
                            data_loc = ChartDataLocation(
                                min_col=views_col,
                                min_row=1, # Include header for series name
                                max_col=views_col,
                                max_row=max_row,
                                title_from_data=True,
                                cats_min_col=title_col
                            )
                            chart_config = ChartConfig(
                                title=f"Top {v_type} Views",
                                x_axis_title="Video Title",
                                y_axis_title="Views"
                            )

                            # Dynamic anchor: 2 columns to the right of the table
                            anchor_col = get_column_letter(max_col + 2)

                            chart_builder.add_bar_chart(
                                data_loc=data_loc,
                                config=chart_config,
                                anchor=f"{anchor_col}2"
                            )

            # 2. Strategy Sheet
            pd.DataFrame({'Gemini Analysis': [strategy]}).to_excel(
                writer, sheet_name="Strategy", index=False
            )
            ws_strat = writer.sheets["Strategy"]
            self._apply_header_style(ws_strat)
            ws_strat.column_dimensions['A'].width = 100
            ws_strat['A2'].alignment = Alignment(wrap_text=True, horizontal='left', vertical='top')
