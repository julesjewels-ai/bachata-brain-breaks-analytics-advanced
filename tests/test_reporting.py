import os
import pandas as pd
from src.core.reporting import ExcelReportGenerator
from openpyxl import load_workbook

def test_excel_generation_renaming(tmp_path):
    """
    Verify that the Excel report generator correctly renames columns
    and applies number formatting.
    """
    generator = ExcelReportGenerator()

    # Create dummy data
    df = pd.DataFrame({
        'video_id': ['vid_1'],
        'title': ['Test Video'],
        'views': [1000],
        'retention_avg_pct': [50.5],
        'type': ['Long']
    })
    anomalies = {'Long': df}
    strategy = "Test Strategy"

    filepath = tmp_path / "test_report.xlsx"
    generator.generate_excel(anomalies, strategy, str(filepath))

    assert os.path.exists(filepath)

    # Verify content and headers with pandas
    df_read = pd.read_excel(filepath, sheet_name="Long Anomalies")
    expected_headers = ['Video ID', 'Video Title', 'Views', 'Retention', 'Type']
    assert list(df_read.columns) == expected_headers

    # Verify number formats with openpyxl
    wb = load_workbook(filepath)
    ws = wb["Long Anomalies"]

    # Header row is 1, data row is 2
    # Columns in expected_headers order:
    # 1: Video ID, 2: Video Title, 3: Views, 4: Retention, 5: Type

    views_cell = ws.cell(row=2, column=3)
    retention_cell = ws.cell(row=2, column=4)

    assert views_cell.number_format == '#,##0'
    assert retention_cell.number_format == '0.00"%"'
