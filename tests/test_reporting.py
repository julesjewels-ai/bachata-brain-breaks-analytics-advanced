import os
import json
import pandas as pd
from openpyxl import load_workbook
from src.core.reporting import ExcelReportStrategy, JSONReportStrategy, CompositeReportGenerator
from src.core.excel_styling import ExcelStyler

def test_excel_strategy_generation(tmp_path):
    """Test that Excel report is generated correctly."""
    # Setup
    strategy = ExcelReportStrategy()
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
    strategy_text = "Test Strategy"
    base_filename = str(tmp_path / "test_report")

    # Execute
    strategy.generate(anomalies, strategy_text, base_filename)

    # Verify
    filepath = base_filename + ".xlsx"
    assert os.path.exists(filepath)
    wb = load_workbook(filepath)
    assert 'Shorts Anomalies' in wb.sheetnames

    # Check content
    ws = wb['Shorts Anomalies']
    assert ws['A2'].value == '1' # video_id

def test_json_strategy_generation(tmp_path):
    """Test that JSON report is generated correctly."""
    # Setup
    strategy = JSONReportStrategy()
    anomalies = {
        'Shorts': pd.DataFrame({
            'video_id': ['1'],
            'title': ['A'],
            'views': [100],
            'retention_avg_pct': [50.0],
            'type': ['Shorts'],
            'publish_date': ['2023-01-01']
        })
    }
    strategy_text = "Test Strategy"
    base_filename = str(tmp_path / "test_report")

    # Execute
    strategy.generate(anomalies, strategy_text, base_filename)

    # Verify
    filepath = base_filename + ".json"
    assert os.path.exists(filepath)

    with open(filepath, 'r') as f:
        data = json.load(f)
        assert data['strategy'] == strategy_text
        assert 'Shorts' in data['anomalies']
        assert len(data['anomalies']['Shorts']) == 1
        assert data['anomalies']['Shorts'][0]['video_id'] == '1'

def test_composite_generator(tmp_path):
    """Test that CompositeReportGenerator generates all reports."""
    # Setup
    excel_strat = ExcelReportStrategy()
    json_strat = JSONReportStrategy()
    composite = CompositeReportGenerator([excel_strat, json_strat])

    anomalies = {
        'Shorts': pd.DataFrame({
            'video_id': ['1'],
            'title': ['A'],
            'views': [100],
            'retention_avg_pct': [50.0],
            'type': ['Shorts'],
            'publish_date': ['2023-01-01']
        })
    }
    strategy_text = "Test Strategy"
    base_filename = str(tmp_path / "test_report_composite")

    # Execute
    composite.generate(anomalies, strategy_text, base_filename)

    # Verify
    assert os.path.exists(base_filename + ".xlsx")
    assert os.path.exists(base_filename + ".json")

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
