import pytest
import pandas as pd
import openpyxl
from src.core.reporting import ExcelReportGenerator
import tempfile
import os

def test_excel_conditional_formatting():
    # 1. Setup Data
    anomalies = {
        'Shorts': pd.DataFrame({
            'video_id': ['1', '2'],
            'title': ['Video A', 'Video B'],
            'views': [1000, 5000],
            'retention_avg_pct': [50.0, 80.0],
            'type': ['Shorts', 'Shorts'],
            'publish_date': ['2023-01-01', '2023-01-02']
        })
    }
    strategy = "Test Strategy"

    # 2. Generate Excel
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        filepath = tmp.name

    try:
        generator = ExcelReportGenerator()
        generator.generate_excel(anomalies, strategy, filepath)

        # 3. Load and Verify
        wb = openpyxl.load_workbook(filepath)
        ws = wb['Shorts Anomalies']

        # Check for conditional formatting
        found_views_bar = False
        found_retention_bar = False

        # openpyxl < 3.0: ws.conditional_formatting.keys()
        # openpyxl >= 3.0: ws.conditional_formatting is iterable

        for cf in ws.conditional_formatting:
            # Check if this CF block has a DataBar rule
            is_databar = any(rule.type == 'dataBar' for rule in cf.rules)
            if is_databar:
                # Check ranges
                # cf.sqref is a generic object, can be converted to string
                ranges = str(cf.sqref)
                if 'C' in ranges: # Views is likely column C
                    found_views_bar = True
                if 'D' in ranges: # Retention is likely column D
                    found_retention_bar = True

        assert found_views_bar, "Views column should have DataBar conditional formatting"
        assert found_retention_bar, "Retention column should have DataBar conditional formatting"

    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
