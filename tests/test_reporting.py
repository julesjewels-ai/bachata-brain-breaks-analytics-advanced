"""
Tests for the reporting module.
"""
import pandas as pd
from openpyxl import load_workbook
from src.core.reporting import ExcelReportGenerator

def test_conditional_formatting_applied(tmp_path):
    """Test that conditional formatting (Data Bars and Color Scales) is applied."""
    filepath = tmp_path / "test_report.xlsx"
    generator = ExcelReportGenerator()

    # Create dummy data
    data = pd.DataFrame({
        'video_id': ['1', '2'],
        'title': ['Video A', 'Video B'],
        'views': [1000, 2000],
        'retention_avg_pct': [50.0, 75.0],
        'type': ['Shorts', 'Shorts']
    })
    anomalies = {'Shorts': data}
    strategy = "Test Strategy"

    # Generate report
    generator.generate_excel(anomalies, strategy, str(filepath))

    # Load workbook and check formatting
    wb = load_workbook(filepath)
    ws = wb['Shorts Anomalies']

    # Check that we have conditional formatting rules
    found_data_bar = False
    found_color_scale = False

    # Iterate through conditional formatting rules
    # ws.conditional_formatting is a ConditionalFormattingList
    # It contains ConditionalFormatting objects (which map ranges to rules)
    for cf in ws.conditional_formatting:
        for rule in cf.rules:
            if rule.type == 'dataBar':
                found_data_bar = True
            if rule.type == 'colorScale':
                found_color_scale = True

    assert found_data_bar, "DataBar rule not found"
    assert found_color_scale, "ColorScale rule not found"
