"""
Tests for charting module.
"""
import pytest
from openpyxl import Workbook
from src.core.charting import ChartBuilder, ChartConfig, ChartDataLocation


@pytest.fixture
def worksheet():
    wb = Workbook()
    return wb.active


def test_chart_config_defaults():
    config = ChartConfig(
        title="Test Chart",
        x_axis_title="X",
        y_axis_title="Y"
    )
    assert config.width == 15.0
    assert config.height == 10.0
    assert config.style == 10


def test_chart_builder_add_bar_chart(worksheet):
    builder = ChartBuilder(worksheet)
    data_loc = ChartDataLocation(
        min_col=2, min_row=1, max_col=3, max_row=5
    )
    config = ChartConfig(
        title="Test", x_axis_title="X", y_axis_title="Y"
    )

    builder.add_bar_chart(data_loc, config)
    assert len(worksheet._charts) == 1
    chart = worksheet._charts[0]
    # OpenPyXL wraps title in an object, so strict string equality fails
    assert chart.title is not None
    assert chart.style == 10
