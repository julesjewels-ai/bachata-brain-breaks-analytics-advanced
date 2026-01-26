"""
Tests for the ExcelReportGenerator in reporting.py.
"""
import pytest
import pandas as pd
import openpyxl
from src.core.reporting import ExcelReportGenerator, ReportConfig

def test_report_config_validation():
    """Test security validation for report paths."""
    with pytest.raises(ValueError, match="must be an Excel"):
        ReportConfig(filepath="test.csv")

    with pytest.raises(ValueError, match="Path traversal"):
        ReportConfig(filepath="../test.xlsx")

    with pytest.raises(ValueError, match="invalid characters"):
        ReportConfig(filepath="test$file.xlsx")

    config = ReportConfig(filepath="valid_report.xlsx")
    assert config.filepath == "valid_report.xlsx"

def test_generate_excel_integration(tmp_path):
    """Integration test for generating a real Excel file."""
    # Setup data
    anomalies = {
        "Shorts": pd.DataFrame({
            "video_id": ["vid_1", "vid_2"],
            "title": ["Video A", "Video B"],
            "views": [1000, 2000],
            "retention_avg_pct": [50.0, 60.0],
            "type": ["Shorts", "Shorts"],
            "publish_date": ["2023-01-01", "2023-01-02"]
        })
    }
    strategy = "Test Strategy"
    output_file = tmp_path / "test_report.xlsx"

    generator = ExcelReportGenerator()
    generator.generate_excel(anomalies, strategy, str(output_file))

    assert output_file.exists()

    # Verify content
    wb = openpyxl.load_workbook(output_file)
    assert "Shorts Anomalies" in wb.sheetnames
    assert "Strategy" in wb.sheetnames

    # Check Header
    ws = wb["Shorts Anomalies"]
    headers = [cell.value for cell in ws[1]]
    assert "Views" in headers
    assert "Video Title" in headers

    # Check data
    assert ws["C2"].value == 1000 # Views column (mapped from 'views')

    # Check strategy sheet
    ws_strat = wb["Strategy"]
    assert ws_strat["A2"].value == "Test Strategy"

def test_generate_excel_empty_anomalies(tmp_path):
    """Test generation when anomalies are empty."""
    anomalies = {
        "Shorts": pd.DataFrame()
    }
    output_file = tmp_path / "empty_report.xlsx"

    generator = ExcelReportGenerator()
    generator.generate_excel(anomalies, "Strategy", str(output_file))

    assert output_file.exists()
    wb = openpyxl.load_workbook(output_file)
    # Should only have Strategy sheet (or empty anomalies sheet is skipped?)
    # Logic: if not df.empty: create sheet.
    assert "Shorts Anomalies" not in wb.sheetnames
    assert "Strategy" in wb.sheetnames
