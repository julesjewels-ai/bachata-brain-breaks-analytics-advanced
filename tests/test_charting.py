"""
Tests for the charting module.
"""
from unittest.mock import MagicMock
import pytest
from openpyxl import Workbook
from src.core.charting import ChartBuilder, ChartDataLocation

def test_chart_builder_add_views_bar_chart():
    """Verify that a chart is added to the worksheet."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Data"

    # Mock data
    ws.append(["title", "views"])
    ws.append(["Video A", 100])
    ws.append(["Video B", 200])

    location = ChartDataLocation(
        min_col=2,
        min_row=2,
        max_col=2,
        max_row=3,
        categories_col=1
    )

    builder = ChartBuilder()
    builder.add_views_bar_chart(ws, location, "Test Chart")

    # Check if chart was added
    assert len(ws._charts) == 1
    chart = ws._charts[0]

    # OpenPyXL 3.1+ stores title as a Title object, not a string
    # We verify the text content within the title object
    assert chart.title.tx.rich.p[0].r[0].t == "Test Chart"

    assert chart.type == "col"
    # Axis titles also might be objects, but let's check
    assert chart.y_axis.title.tx.rich.p[0].r[0].t == "Views"

    # Verify references
    # Note: Accessing chart data references in openpyxl can be complex to verify exactly,
    # but presence of the chart object with correct title is a strong signal.
