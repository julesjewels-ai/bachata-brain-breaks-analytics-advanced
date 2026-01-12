import pytest
from openpyxl import Workbook
from src.core.reporting import ExcelReportGenerator

def test_adjust_column_widths():
    wb = Workbook()
    ws = wb.active

    # Add some data
    ws['A1'] = "Short"
    ws['A2'] = "A very long string that should determine width"
    ws['B1'] = "Medium Length"
    ws['B2'] = None

    ExcelReportGenerator._adjust_column_widths(ws)

    # Check widths
    # Width should be length of longest string + 2
    # Column A: max length is len("A very long string that should determine width") = 46. Width -> 48
    # Column B: max length is len("Medium Length") = 13. Width -> 15

    assert ws.column_dimensions['A'].width == len("A very long string that should determine width") + 2
    assert ws.column_dimensions['B'].width == len("Medium Length") + 2
