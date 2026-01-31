import pytest
from unittest.mock import MagicMock, patch, ANY
from io import BytesIO
import pandas as pd
from PIL import Image
from src.core.reporting import ExcelReportGenerator

@pytest.fixture
def mock_anomalies():
    return {
        'TestType': pd.DataFrame({
            'video_id': ['1'],
            'title': ['Test Video'],
            'views': [1000],
            'retention_avg_pct': [50.0],
            'type': ['Shorts'],
            'publish_date': ['2023-01-01']
        })
    }

def test_safe_load_image_verify_called(mock_anomalies, tmp_path):
    """
    Test that the image loading mechanism verifies the image integrity.
    """
    generator = ExcelReportGenerator()
    filepath = str(tmp_path / "test_report.xlsx")

    img_buf = BytesIO(b"fake_image_data")

    with patch('src.core.reporting.MatplotlibVisualizer') as MockViz:
        mock_instance = MockViz.return_value
        mock_instance.generate_chart.return_value = img_buf

        # Mock PIL.Image.open
        with patch('src.core.reporting.PILImage.open') as mock_open:
            mock_img = MagicMock()
            # Context manager support
            mock_open.return_value.__enter__.return_value = mock_img

            # The current code in reporting.py calls PILImage.open(img_stream)
            # It does NOT call verify().
            # So this test should FAIL if I assert verify() was called.

            try:
                generator.generate_excel(mock_anomalies, "Strategy", filepath)
            except Exception:
                # Ignore other errors (like invalid image data)
                pass

            # This assertion validates that .verify() is called on the image object
            mock_img.verify.assert_called_once()

def test_safe_load_image_limit_set(mock_anomalies, tmp_path):
    """
    Test that Image.MAX_IMAGE_PIXELS is set to the safe limit.
    """
    generator = ExcelReportGenerator()
    filepath = str(tmp_path / "test_report.xlsx")

    img_buf = BytesIO(b"fake_image_data")

    with patch('src.core.reporting.MatplotlibVisualizer') as MockViz:
        mock_instance = MockViz.return_value
        mock_instance.generate_chart.return_value = img_buf

        with patch('src.core.reporting.PILImage.open') as mock_open:
            mock_img = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_img

            # Reset global to a known unsafe value
            Image.MAX_IMAGE_PIXELS = None

            try:
                generator.generate_excel(mock_anomalies, "Strategy", filepath)
            except Exception:
                pass

            # This assertion checks if the limit was applied
            assert Image.MAX_IMAGE_PIXELS == 50_000_000
