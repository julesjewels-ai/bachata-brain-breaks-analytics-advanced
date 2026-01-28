import os
import pandas as pd
import pytest
from openpyxl import load_workbook
from src.core.services.excel_report_service import ExcelReportService

def test_excel_generation_conditional_formatting(tmp_path, monkeypatch):
    """Test that conditional formatting (DataBars) is applied to specific columns."""
    # Setup
    monkeypatch.chdir(tmp_path)
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
    filepath = "test_report.xlsx"

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
    # Currently we expect 0 or failure to find specific rules

    data_bar_rules = 0
    for cf in rules:
        # Each cf object has a list of rules (cf.rules)
        for rule in cf.rules:
            if rule.type == 'dataBar':
                data_bar_rules += 1

    # This assertion should fail before implementation
    assert data_bar_rules >= 2, f"Expected at least 2 data bar rules, found {data_bar_rules}"
