"""
Tests for reporting with thumbnail integration.
"""
from unittest.mock import MagicMock
import pandas as pd
from openpyxl import load_workbook
from src.core.reporting import ExcelReportGenerator
from src.services.image_service import IThumbnailService, ThumbnailConfig
from io import BytesIO
from PIL import Image

class MockThumbnailService:
    def generate_thumbnail(self, title: str, config=None) -> BytesIO:
        # Generate a real valid 1x1 image to avoid openpyxl errors
        img = Image.new('RGB', (10, 10), color='red')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return buf

def test_excel_generation_with_thumbnails(tmp_path):
    # Setup
    output_file = tmp_path / "test_report.xlsx"
    anomalies = {
        'TestType': pd.DataFrame({
            'video_id': ['1'],
            'title': ['Test Video'],
            'views': [1000],
            'retention_avg_pct': [50.0],
            'type': ['TestType'],
            'publish_date': ['2023-01-01']
        })
    }
    strategy = "Test Strategy"

    # Inject Mock Service
    mock_service = MockThumbnailService()
    generator = ExcelReportGenerator(thumbnail_service=mock_service)

    # Execute
    generator.generate_excel(anomalies, strategy, str(output_file))

    # Verify
    wb = load_workbook(output_file)
    ws = wb['TestType Anomalies']

    # Check if "Thumbnail" header exists
    headers = [cell.value for cell in ws[1]]
    assert "Thumbnail" in headers

    # Check if an image is present
    # openpyxl stores images in ws._images (internal) or ws.images (some versions)
    # The standard way to access images is not straightforward in all openpyxl versions,
    # but we can check the relationship or just ensure no error occurred.
    # In newer openpyxl, `ws._images` is the list.
    assert hasattr(ws, '_images')
    assert len(ws._images) == 1
