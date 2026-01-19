"""
Charting module for generating visualizations in Excel reports.
Decouples visual generation from data reporting logic.
"""
from typing import Optional
from openpyxl.chart import BarChart, Reference # type: ignore
from openpyxl.worksheet.worksheet import Worksheet # type: ignore
from pydantic import BaseModel, Field, field_validator

class ChartDataLocation(BaseModel):
    """
    Defines the coordinates for chart data within a worksheet.
    """
    min_col: int = Field(..., gt=0)
    min_row: int = Field(..., gt=0)
    max_col: int = Field(..., gt=0)
    max_row: int = Field(..., gt=0)

    @field_validator('max_col')
    @classmethod
    def validate_cols(cls, v: int, info) -> int:
        if 'min_col' in info.data and v < info.data['min_col']:
            raise ValueError("max_col must be >= min_col")
        return v

    @field_validator('max_row')
    @classmethod
    def validate_rows(cls, v: int, info) -> int:
        if 'min_row' in info.data and v < info.data['min_row']:
            raise ValueError("max_row must be >= min_row")
        return v

class ChartBuilder:
    """
    Service for building OpenPyXL charts.
    """

    @staticmethod
    def build_bar_chart(
        ws: Worksheet,
        data_loc: ChartDataLocation,
        title: str,
        x_axis_title: str = "",
        y_axis_title: str = "",
        categories_loc: Optional[ChartDataLocation] = None
    ) -> BarChart:
        """
        Creates a BarChart using the specified data and categories.
        """
        chart = BarChart()
        chart.title = title
        chart.style = 10  # Standard style
        chart.y_axis.title = y_axis_title
        chart.x_axis.title = x_axis_title

        # Add Data
        data = Reference(
            ws,
            min_col=data_loc.min_col,
            min_row=data_loc.min_row,
            max_col=data_loc.max_col,
            max_row=data_loc.max_row
        )
        chart.add_data(data, titles_from_data=True)

        # Add Categories (if provided)
        if categories_loc:
            cats = Reference(
                ws,
                min_col=categories_loc.min_col,
                min_row=categories_loc.min_row,
                max_col=categories_loc.max_col,
                max_row=categories_loc.max_row
            )
            chart.set_categories(cats)

        return chart
