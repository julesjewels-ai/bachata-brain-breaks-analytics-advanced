
import pandas as pd
import pytest
from src.core.reporting import ExcelReportGenerator
from openpyxl import load_workbook
import os

def test_excel_report_generation_cf():
    """
    Test that the Excel report is generated with conditional formatting.
    Initially, this test will verify the absence of CF, and later the presence.
    """
    filepath = "test_report.xlsx"

    # Cleanup before test
    if os.path.exists(filepath):
        os.remove(filepath)

    try:
        # 1. Setup Data
        data = {
            'video_id': ['vid_1', 'vid_2', 'vid_3'],
            'title': ['Video A', 'Video B', 'Video C'],
            'views': [1000, 5000, 10000],
            'retention_avg_pct': [20.5, 60.0, 95.5],
            'type': ['Shorts', 'Shorts', 'Shorts'],
            'publish_date': ['2023-01-01', '2023-01-02', '2023-01-03']
        }
        df = pd.DataFrame(data)
        anomalies = {'Shorts': df}
        strategy = "Test Strategy"

        # 2. Generate Report
        generator = ExcelReportGenerator()
        generator.generate_excel(anomalies, strategy, filepath)

        # 3. Verify Output
        assert os.path.exists(filepath)

        wb = load_workbook(filepath)
        ws = wb["Shorts Anomalies"]

        # Check for Conditional Formatting
        # We expect 2 rules (Views, Retention) eventually.
        # Initially, we expect 0 or simply check what's there.

        cf_rules = list(ws.conditional_formatting)
        print(f"DEBUG: Found {len(cf_rules)} CF rules.")

        # Verify Conditional Formatting Rules
        # We expect at least 2 rules (one for Views, one for Retention)
        # Note: OpenPyXL might store them as separate items in the iterable

        has_databar = False
        for cf in cf_rules:
            # cf is usually a ConditionalFormatting object which contains rules
            for rule in cf.rules:
                if rule.type == 'dataBar':
                    has_databar = True
                    # Optional: Check color
                    # print(f"DataBar Color: {rule.dataBar.color.rgb}")

        assert has_databar, "Expected at least one DataBar rule for conditional formatting."

        assert ws.title == "Shorts Anomalies"
        assert ws['C1'].value == "Views" # Check header mapping
        assert ws['D1'].value == "Retention (%)"

    finally:
        # Cleanup
        if os.path.exists(filepath):
            os.remove(filepath)

if __name__ == "__main__":
    test_excel_report_generation_cf()
