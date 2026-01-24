"""
Reporting module for generating Excel reports.
Handles styling and formatting logic for Excel output.
"""
from typing import Dict, Optional
import io
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image
from pydantic import BaseModel, Field, ValidationError, field_validator
import re

from src.core.charting import ChartBuilder, ChartConfig, ChartDataLocation
from src.core.interfaces import IReportGenerator, ReportRequest


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

    def generate_report(self, request: ReportRequest, visuals: Dict[str, io.BytesIO]) -> None:
        """
        Generates an Excel report with anomalies and strategy analysis, embedding visuals.
        """
        try:
            config = ReportConfig(filepath=request.filepath)
            safe_path = config.filepath
        except ValidationError as e:
            raise ValueError(f"Security validation failed: {e}")

        with pd.ExcelWriter(safe_path, engine='openpyxl') as writer:
            # 1. Anomalies Sheets
            for v_type, df in request.anomalies.items():
                if not df.empty:
                    sheet_name = f"{v_type} Anomalies"
                    # Rename columns for better readability
                    display_df = df.rename(columns=self.COLUMN_MAPPING)
                    display_df.to_excel(writer, sheet_name=sheet_name, index=False)
                    ws = writer.sheets[sheet_name]
                    self._apply_header_style(ws)
                    self._apply_number_formats(ws)
                    self._adjust_column_widths(ws)

                    # Calculate anchor for charts/visuals
                    max_col = ws.max_column
                    anchor_col_idx = max_col + 2
                    anchor_col = get_column_letter(anchor_col_idx)

                    # Add Bar Chart (Native)
                    headers = {cell.value: cell.column for cell in ws[1]}
                    if 'Views' in headers and 'Video Title' in headers:
                        views_col = headers['Views']
                        title_col = headers['Video Title']
                        max_row = ws.max_row

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
                            ) # type: ignore

                            chart_builder.add_bar_chart(
                                data_loc=data_loc,
                                config=chart_config,
                                anchor=f"{anchor_col}2"
                            )

                    # Embed Visuals (e.g., Heatmaps)
                    # We look for a visual key matching the video type (e.g. 'Long', 'Shorts')
                    if v_type in visuals:
                        img_stream = visuals[v_type]
                        # Reset stream position just in case
                        img_stream.seek(0)

                        try:
                            img = Image(img_stream)
                            # Place it to the right of the bar chart (approx + 8 columns from chart start)
                            # Bar chart is at anchor_col. Let's put image at anchor_col + 8
                            visual_anchor = get_column_letter(anchor_col_idx + 8) + "2"
                            ws.add_image(img, visual_anchor)
                        except Exception as e:
                            # Log or ignore if image fails, to not break report generation
                            print(f"Warning: Failed to embed visual for {v_type}: {e}")

            # 2. Strategy Sheet
            pd.DataFrame({'Gemini Analysis': [request.strategy]}).to_excel(
                writer, sheet_name="Strategy", index=False
            )
            ws_strat = writer.sheets["Strategy"]
            self._apply_header_style(ws_strat)
            ws_strat.column_dimensions['A'].width = 100
            ws_strat['A2'].alignment = Alignment(wrap_text=True, horizontal='left', vertical='top')

    def generate_excel(self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str):
        """Deprecated: Use generate_report instead. Kept for backward compatibility."""
        request = ReportRequest(anomalies=anomalies, strategy=strategy, filepath=filepath)
        self.generate_report(request, visuals={})
