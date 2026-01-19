"""
Tests for the charting module.
"""
import pytest
from openpyxl import Workbook
from src.core.charting import ChartBuilder, ChartDataLocation

def test_chart_data_location_validation():
    """Test validation logic for data coordinates."""
    # Valid
    ChartDataLocation(min_col=1, min_row=1, max_col=2, max_row=2)

    # Invalid max_col < min_col
    with pytest.raises(ValueError, match="max_col must be >= min_col"):
        ChartDataLocation(min_col=2, min_row=1, max_col=1, max_row=1)

    # Invalid max_row < min_row
    with pytest.raises(ValueError, match="max_row must be >= min_row"):
        ChartDataLocation(min_col=1, min_row=2, max_col=1, max_row=1)

def test_build_bar_chart():
    """Test that a BarChart is correctly created."""
    wb = Workbook()
    ws = wb.active

    # Add dummy data
    ws['A1'] = "Title"
    ws['B1'] = "Views"
    ws['A2'] = "Video 1"
    ws['B2'] = 100
    ws['A3'] = "Video 2"
    ws['B3'] = 200

    data_loc = ChartDataLocation(min_col=2, min_row=1, max_col=2, max_row=3)
    cats_loc = ChartDataLocation(min_col=1, min_row=2, max_col=1, max_row=3)

    chart = ChartBuilder.build_bar_chart(
        ws=ws,
        data_loc=data_loc,
        categories_loc=cats_loc,
        title="Test Chart",
        x_axis_title="Videos",
        y_axis_title="View Count"
    )

    # Assertions
    # Note: Immediately after creation, title is often just the string or property assigned.
    # OpenPyXL converts it to nested objects upon serialization usually.
    # We check if it matches what we assigned.
    # Update: OpenPyXL 3.1+ converts string titles to objects immediately.
    assert chart.title.tx.rich.p[0].r[0].t == "Test Chart"
    assert chart.x_axis.title.tx.rich.p[0].r[0].t == "Videos"
    assert chart.y_axis.title.tx.rich.p[0].r[0].t == "View Count"

    # Check that data was added (at least one series)
    assert len(chart.series) == 1
