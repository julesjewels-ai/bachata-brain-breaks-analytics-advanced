"""
Charting module for creating visualization components.
Follows SOLID principles by decoupling chart generation from report generation.
"""
from typing import Optional
from openpyxl.chart import BarChart, Reference
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, Field, field_validator

class ChartDataLocation(BaseModel):
    """
    Defines the location of data within an Excel sheet.
    Used to decouple data coordinates from the chart logic.
    """
    min_col: int = Field(..., gt=0)
    min_row: int = Field(..., gt=0)
    max_col: int = Field(..., gt=0)
    max_row: int = Field(..., gt=0)

    @field_validator('max_col')
    @classmethod
    def validate_max_col(cls, v: int, info) -> int:
        if 'min_col' in info.data and v < info.data['min_col']:
            raise ValueError("max_col must be greater than or equal to min_col")
        return v

    @field_validator('max_row')
    @classmethod
    def validate_max_row(cls, v: int, info) -> int:
        if 'min_row' in info.data and v < info.data['min_row']:
            raise ValueError("max_row must be greater than or equal to min_row")
        return v

class ChartConfig(BaseModel):
    """
    Configuration for chart creation.
    """
    title: str
    x_axis_title: str
    y_axis_title: str
    data_location: ChartDataLocation
    categories_location: Optional[ChartDataLocation] = None
    width: float = 15.0
    height: float = 10.0

class ChartBuilder:
    """
    Service responsible for building OpenPyXL chart objects.
    Isolates charting logic from report generation logic.
    """

    def build_bar_chart(self, worksheet: Worksheet, config: ChartConfig) -> BarChart:
        """
        Creates a BarChart based on the provided configuration.
        """
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = config.title
        chart.y_axis.title = config.y_axis_title
        chart.x_axis.title = config.x_axis_title
        # OpenPyXL types imply width/height are floats, but mypy might think otherwise
        # or there is a mismatch in stubs.
        # We explicitly cast if needed, but here it seems mypy thinks chart.width is int?
        # Let's inspect stubs or just accept float as valid for runtime.
        chart.width = config.width # type: ignore
        chart.height = config.height

        # Define data reference
        data = Reference(
            worksheet,
            min_col=config.data_location.min_col,
            min_row=config.data_location.min_row,
            max_col=config.data_location.max_col,
            max_row=config.data_location.max_row
        )
        # titles_from_data=True assumes the first row of selection is titles
        chart.add_data(data, titles_from_data=True)

        if config.categories_location:
            cats = Reference(
                worksheet,
                min_col=config.categories_location.min_col,
                min_row=config.categories_location.min_row,
                max_row=config.categories_location.max_row
                # max_col is implied to be same as min_col usually for categories
            )
            chart.set_categories(cats)

        return chart
