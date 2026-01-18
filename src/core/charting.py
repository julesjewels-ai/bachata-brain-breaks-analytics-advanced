"""
Charting module for creating visual representations of analytics data.
Decoupled from the main reporting logic to adhere to Single Responsibility Principle.
"""
from openpyxl.chart import BarChart, Reference
from openpyxl.worksheet.worksheet import Worksheet
from pydantic import BaseModel, Field


class ChartDataLocation(BaseModel):
    """
    Specifies where the data for the chart is located in the worksheet.
    Used to decouple chart generation from data layout knowledge.
    """
    min_col: int = Field(..., description="Starting column index (1-based) of the data series")
    min_row: int = Field(..., description="Starting row index of the data series")
    max_col: int = Field(..., description="Ending column index of the data series")
    max_row: int = Field(..., description="Ending row index of the data series")
    categories_col: int = Field(..., description="Column index for x-axis labels (categories)")


class ChartBuilder:
    """
    Service responsible for adding visualization components to Excel worksheets.
    """

    def add_views_bar_chart(self, ws: Worksheet, location: ChartDataLocation, title: str) -> None:
        """
        Adds a bar chart comparing views for the given data range.

        Args:
            ws: The OpenPyXL worksheet to add the chart to.
            location: A ChartDataLocation object defining the data range.
            title: The title of the chart.
        """
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = title
        chart.y_axis.title = 'Views'
        chart.x_axis.title = 'Video Title'
        chart.height = 10  # Height in centimeters (approx)
        chart.width = 18   # Width in centimeters (approx)

        # Data: The numerical values (e.g., Views)
        # min_row includes the header for proper series naming if titles_from_data=True
        data = Reference(
            ws,
            min_col=location.min_col,
            min_row=location.min_row - 1,  # Assuming header is immediately above data
            max_col=location.max_col,
            max_row=location.max_row
        )

        # Categories: The labels (e.g., Video Titles)
        cats = Reference(
            ws,
            min_col=location.categories_col,
            min_row=location.min_row,
            max_row=location.max_row
        )

        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)

        # Place the chart below the data table, with some padding
        chart_position = f"A{location.max_row + 3}"
        ws.add_chart(chart, chart_position)
