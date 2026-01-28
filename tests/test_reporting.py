import os
import pandas as pd
import pytest
from openpyxl import load_workbook
from src.core.services.excel_report_service import ExcelReportService

def test_excel_generation_conditional_formatting(tmp_path):
    """Test that conditional formatting (DataBars) is applied to specific columns."""
    # Setup
    generator = ExcelReportService()
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
    generator.generate_report(anomalies, strategy, filepath)

    # Verify
    assert os.path.exists(filepath)
    wb = load_workbook(filepath)
    ws = wb['Shorts Anomalies']

    # Check for conditional formatting
    rules = list(ws.conditional_formatting)

    data_bar_rules = 0
    for cf in rules:
        for rule in cf.rules:
            if rule.type == 'dataBar':
                data_bar_rules += 1

    assert data_bar_rules >= 2, f"Expected at least 2 data bar rules, found {data_bar_rules}"
