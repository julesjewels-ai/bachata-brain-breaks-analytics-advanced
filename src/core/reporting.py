"""
Reporting module for generating Excel reports.
Handles styling and formatting logic for Excel output.
"""
from typing import Dict, Optional
from numbers import Number
import logging
import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from openpyxl.formatting.rule import DataBarRule
from openpyxl.worksheet.worksheet import Worksheet
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage
from pydantic import BaseModel, Field, ValidationError, field_validator
import re

from src.core.charting import ChartBuilder, ChartConfig, ChartDataLocation
from src.core.visualization import MatplotlibVisualizer

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
    def _estimate_cell_width(cell) -> int:
        """Estimates the display width of a cell based on value and number format."""
        if cell.value is None:
            return 0

        val = cell.value
        fmt = cell.number_format

        if isinstance(val, Number) and fmt:
            width = ExcelReportGenerator._get_formatted_width(val, fmt)
            if width:
                return width

        return len(str(val))

    @staticmethod
    def _get_formatted_width(val: Number, fmt: str) -> Optional[int]:
        """Helper to calculate width for specific Excel number formats."""
        # Thousands separator (e.g., #,##0)
        if '#,##0' in fmt:
            precision = 2 if '.00' in fmt else 0
            return len(f"{val:,.{precision}f}")

        # Percentage (e.g., 0.00%)
        if '0.00%' in fmt or '0.00"%"' in fmt:
            return len(f"{val:.2f}%")

        return None

    @staticmethod
    def _adjust_column_widths(ws):
        """Auto-adjusts column widths based on content length with min/max constraints."""
        min_width = 10
        max_width = 50
        for col in ws.columns:
            # Calculate max length of data in column
            max_length = 0
            for cell in col:
                cell_width = ExcelReportGenerator._estimate_cell_width(cell)
                max_length = max(max_length, cell_width)

            # Apply padding and clamp between min and max
            adjusted_width = max(min_width, min(max_length + 2, max_width))
            ws.column_dimensions[get_column_letter(col[0].column)].width = adjusted_width

    @staticmethod
    def _get_header_map(ws: Worksheet) -> Dict[str, int]:
        """Returns a map of header name to column index (1-based)."""
        return {str(cell.value): cell.column for cell in ws[1] if cell.value is not None}

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

        headers = ExcelReportGenerator._get_header_map(ws)

        for header, fmt in format_map.items():
            if header in headers:
                col_idx = headers[header]
                # Apply format to all cells in the column (skipping header)
                for row in range(2, ws.max_row + 1):
                    ws.cell(row=row, column=col_idx).number_format = fmt

    @staticmethod
    def _apply_conditional_formatting(ws):
        """Applies data bars to visualization columns."""
        # Define rules
        # Blue for Views, Green for Retention
        rules = {
            'Views': DataBarRule(start_type='min', end_type='max', color="638EC6"),
            'Retention (%)': DataBarRule(start_type='min', end_type='max', color="63C384")
        }

        headers = ExcelReportGenerator._get_header_map(ws)

        for header, rule in rules.items():
            if header in headers:
                col_letter = get_column_letter(headers[header])
                # Apply to the entire column data range (e.g. C2:C100)
                # Ensure we have data
                if ws.max_row > 1:
                    range_ref = f"{col_letter}2:{col_letter}{ws.max_row}"
                    ws.conditional_formatting.add(range_ref, rule)

    def _create_anomaly_sheet(self, writer, v_type: str, df: pd.DataFrame) -> Worksheet:
        """Creates and styles a sheet for anomalies."""
        sheet_name = f"{v_type} Anomalies"
        display_df = df.rename(columns=self.COLUMN_MAPPING)
        display_df.to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]
        self._apply_header_style(ws)
        self._apply_number_formats(ws)
        self._apply_conditional_formatting(ws)
        self._adjust_column_widths(ws)
        return ws

    def _add_anomaly_chart(self, ws: Worksheet, v_type: str) -> None:
        """Adds a bar chart to the anomaly sheet."""
        headers = ExcelReportGenerator._get_header_map(ws)
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

    def _add_strategy_sheet(self, writer, strategy: str) -> None:
        """Creates the strategy analysis sheet."""
        pd.DataFrame({'Gemini Analysis': [strategy]}).to_excel(
            writer, sheet_name="Strategy", index=False
        )
        ws_strat = writer.sheets["Strategy"]
        self._apply_header_style(ws_strat)
        ws_strat.column_dimensions['A'].width = 100
        ws_strat['A2'].alignment = Alignment(wrap_text=True, horizontal='left', vertical='top')

    def _add_visual_insights(self, writer, anomalies: Dict[str, pd.DataFrame]) -> None:
        """Generates and embeds visual insights chart."""
        # Combine all anomalies to one DF for visualization
        all_anomalies = pd.concat(anomalies.values()) if anomalies else pd.DataFrame()
        if not all_anomalies.empty and 'views' in all_anomalies.columns and 'retention_avg_pct' in all_anomalies.columns:
            visualizer = MatplotlibVisualizer()
            try:
                img_stream = visualizer.generate_chart(
                    all_anomalies,
                    title="Views vs Retention Correlation",
                    x_col="retention_avg_pct",
                    y_col="views"
                )

                # Create sheet
                ws_viz = writer.book.create_sheet("Visual Insights")

                # Embed Image
                # OpenPyXL Image requires a path or PIL Image object
                pil_img = PILImage.open(img_stream)
                img = XLImage(pil_img)
                ws_viz.add_image(img, "A1")

                # Add description
                ws_viz["A25"] = "Scatter plot showing relationship between Audience Retention and View Count."
                ws_viz["A25"].font = Font(italic=True, color="555555")

            except Exception as e:
                # Log or handle error without crashing report
                logger.warning(f"Failed to generate visualization: {e}")

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
                    ws = self._create_anomaly_sheet(writer, v_type, df)
                    self._add_anomaly_chart(ws, v_type)

            # 2. Strategy Sheet
            self._add_strategy_sheet(writer, strategy)

            # 3. Visual Insights (Embedded Matplotlib)
            self._add_visual_insights(writer, anomalies)
