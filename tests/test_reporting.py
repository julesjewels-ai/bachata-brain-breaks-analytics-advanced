import os
import pandas as pd
from io import BytesIO
from openpyxl import load_workbook
from src.core.reporting import ExcelReportGenerator
from src.core.excel_styling import ExcelStyler
from src.core.interfaces import Visualizer

class MockVisualizer(Visualizer):
    def generate_chart(self, df: pd.DataFrame, title: str, x_col: str, y_col: str) -> BytesIO:
        # Return a valid minimal PNG signature
        return BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

def test_excel_generation_conditional_formatting(tmp_path):
    """Test that conditional formatting (DataBars) is applied to specific columns."""
    # Setup
    visualizer = MockVisualizer()
    generator = ExcelReportGenerator(visualizer=visualizer)
    anomalies = {
        'Shorts': pd.DataFrame({
            'video_id': ['1', '2'],
            'title': ['A', 'B'],
            'views': [100, 1000],
            'retention_avg_pct': [50.0, 90.0],
            'type': ['Shorts', 'Shorts'],
            'publish_date': ['2023-01-01', '2023-01-02']
        })
    }
    strategy = "Test Strategy"
    filepath = str(tmp_path / "test_report.xlsx")

    # Execute
    generator.generate_excel(anomalies, strategy, filepath)

    # Verify
    assert os.path.exists(filepath)
    wb = load_workbook(filepath)
    ws = wb['Shorts Anomalies']

    # Check for conditional formatting
    # Note: openpyxl stores conditional formatting rules in `ws.conditional_formatting`
    # It behaves like a list-like object but iterating it returns ConditionalFormatting objects

    rules = list(ws.conditional_formatting)

    # Check if we have rules for 'Views' (C column likely) and 'Retention (%)' (D column likely)
    # The header mapping is:
    # 'video_id': 'Video ID' (A)
    # 'title': 'Video Title' (B)
    # 'views': 'Views' (C)
    # 'retention_avg_pct': 'Retention (%)' (D)

    # We expect 2 rules if implemented
    data_bar_rules = 0
    for cf in rules:
        # Each cf object has a list of rules (cf.rules)
        for rule in cf.rules:
            if rule.type == 'dataBar':
                data_bar_rules += 1

    assert data_bar_rules >= 2, f"Expected at least 2 data bar rules, found {data_bar_rules}"


class MockCell:
    def __init__(self, value, number_format=None):
        self.value = value
        self.number_format = number_format

def test_estimate_cell_width():
    """Test the ExcelStyler.estimate_cell_width helper method."""
    # Test None
    assert ExcelStyler.estimate_cell_width(MockCell(None)) == 0

    # Test String
    assert ExcelStyler.estimate_cell_width(MockCell("Hello")) == 5

    # Test Integer
    assert ExcelStyler.estimate_cell_width(MockCell(12345)) == 5

    # Test Float (default)
    assert ExcelStyler.estimate_cell_width(MockCell(12.34)) == 5

    # Test Formatted Number (#,##0)
    # 1234 -> 1,234 (length 5)
    assert ExcelStyler.estimate_cell_width(MockCell(1234, '#,##0')) == 5

    # Test Formatted Number with decimals (#,##0.00)
    # 1234.56 -> 1,234.56 (length 8)
    assert ExcelStyler.estimate_cell_width(MockCell(1234.56, '#,##0.00')) == 8

    # Test Percentage (0.00%)
    # 95.5 -> 95.50% (length 6)
    assert ExcelStyler.estimate_cell_width(MockCell(95.5, '0.00%')) == 6

    # Test Percentage with quotes (0.00"%")
    assert ExcelStyler.estimate_cell_width(MockCell(95.5, '0.00"%"')) == 6

    # Test Unknown Format
    assert ExcelStyler.estimate_cell_width(MockCell(1234, 'General')) == 4
