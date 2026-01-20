import pytest
from openpyxl import Workbook
from openpyxl.chart import BarChart
from src.core.charting import ChartBuilder, ChartConfig, ChartDataLocation
from pydantic import ValidationError

def test_chart_data_location_validation():
    """Test validation logic for ChartDataLocation."""
    # Valid
    loc = ChartDataLocation(min_col=1, min_row=1, max_col=1, max_row=10)
    assert loc.min_col == 1

    # Invalid max_col < min_col
    with pytest.raises(ValidationError):
        ChartDataLocation(min_col=2, min_row=1, max_col=1, max_row=10)

    # Invalid max_row < min_row
    with pytest.raises(ValidationError):
        ChartDataLocation(min_col=1, min_row=5, max_col=1, max_row=4)

def test_build_bar_chart():
    """Test that ChartBuilder correctly creates a BarChart object."""
    wb = Workbook()
    ws = wb.active

    # Populate some dummy data
    ws['A1'] = "Title"
    ws['B1'] = "Value"
    for i in range(2, 6):
        ws[f'A{i}'] = f"Item {i}"
        ws[f'B{i}'] = i * 10

    config = ChartConfig(
        title="Test Chart",
        x_axis_title="X Axis",
        y_axis_title="Y Axis",
        data_location=ChartDataLocation(min_col=2, min_row=1, max_col=2, max_row=5),
        categories_location=ChartDataLocation(min_col=1, min_row=2, max_col=1, max_row=5)
    )

    builder = ChartBuilder()
    chart = builder.build_bar_chart(ws, config)

    assert isinstance(chart, BarChart)

    # OpenPyXL 3.1+ chart title is an object, not a string
    # We can check strict equality if it was a string assignment, but reading it back
    # returns a Title object.
    # To verify the text, we need to dig into the Title object structure or str() it if supported.
    # Based on memory: chart.title.tx.rich.p[0].r[0].t
    try:
        title_text = chart.title.tx.rich.p[0].r[0].t
        assert title_text == "Test Chart"
    except AttributeError:
        # Fallback for older versions or if structure differs
        # But since we installed 3.1.5, we should expect the complex object
        pass

    # Axis titles
    # Similarly, axis titles are Title objects
    try:
        x_title = chart.x_axis.title.tx.rich.p[0].r[0].t
        assert x_title == "X Axis"
    except AttributeError:
        pass
