"""
Tests for reporting module.
"""
import pytest
from unittest.mock import Mock, patch
from openpyxl.worksheet.worksheet import Worksheet
from src.core.reporting import ExcelReportGenerator, ReportConfig


class MockCell:
    def __init__(self, value, number_format="General", font=None):
        self.value = value
        self.number_format = number_format
        self.font = font


class MockFont:
    def __init__(self, bold=False):
        self.bold = bold


def test_estimate_cell_width_string():
    cell = MockCell("Test")
    assert ExcelReportGenerator._estimate_cell_width(cell) == 4


def test_estimate_cell_width_number_formatted():
    cell = MockCell(1000, "#,##0")
    # 1,000 -> 5 chars
    assert ExcelReportGenerator._estimate_cell_width(cell) == 5


def test_estimate_cell_width_percentage():
    cell = MockCell(0.5, "0.00%")
    # 0.50% -> 5 chars
    assert ExcelReportGenerator._estimate_cell_width(cell) == 5


def test_report_config_validation():
    with pytest.raises(ValueError, match="Excel"):
        ReportConfig(filepath="test.txt")

    with pytest.raises(ValueError, match="Path traversal"):
        ReportConfig(filepath="../test.xlsx")

    with pytest.raises(ValueError, match="invalid characters"):
        ReportConfig(filepath="test$file.xlsx")

    config = ReportConfig(filepath="valid/path/test.xlsx")
    assert config.filepath == "valid/path/test.xlsx"


def test_adjust_column_widths_mocked():
    # Mock worksheet and columns
    mock_ws = Mock(spec=Worksheet)
    # 2 columns, 1 row
    c1 = MockCell("Short")
    c2 = MockCell("A very long string that should be clamped")
    mock_ws.columns = [[c1], [c2]]

    # Mock column_dimensions
    mock_ws.column_dimensions = {
        'A': Mock(),
        'B': Mock()
    }

    # Helper to return column letter 'A' then 'B'
    with patch('src.core.reporting.get_column_letter', side_effect=['A', 'B']):
        # We need to ensure c1.column and c2.column work or are mocked.
        # In real openpyxl, cell.column is 1-based index.
        c1.column = 1
        c2.column = 2

        ExcelReportGenerator._adjust_column_widths(mock_ws)

        # Check widths
        # 'Short' -> 5. 5+2=7. Min width 10.
        assert mock_ws.column_dimensions['A'].width == 10
        # Long string -> 41. 41+2=43. Max 50.
        assert mock_ws.column_dimensions['B'].width == 43
