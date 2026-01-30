import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
from PIL import Image
from src.core.reporting import ExcelReportGenerator
import pandas as pd

# Mock data for generate_excel
anomalies_mock = {
    'Shorts': pd.DataFrame({
        'video_id': ['1'],
        'title': ['Test'],
        'views': [100],
        'retention_avg_pct': [50.0],
        'type': ['Shorts'],
        'publish_date': ['2023-01-01']
    })
}
strategy_mock = "Strategy"

def test_excel_generator_safe_load_image_normal():
    """Verify that generate_excel handles normal images correctly."""

    img_stream = BytesIO()
    img = Image.new('RGB', (100, 100), color='red')
    img.save(img_stream, format='PNG')
    img_stream.seek(0)

    with patch('src.core.reporting.MatplotlibVisualizer') as MockViz:
        mock_viz_instance = MockViz.return_value
        mock_viz_instance.generate_chart.return_value = img_stream

        generator = ExcelReportGenerator()
        generator.generate_excel(anomalies_mock, strategy_mock, "test_output.xlsx")

def test_excel_generator_rejects_decompression_bomb():
    """Verify that _safe_load_image rejects images causing DecompressionBombError."""

    generator = ExcelReportGenerator()

    with patch('src.core.reporting.PILImage.open') as mock_open:
        # Simulate DecompressionBombError
        mock_open.side_effect = Image.DecompressionBombError("Image is too large")

        # Verify it raises the secure ValueError
        with pytest.raises(ValueError, match="Security event: Invalid image or potential DoS attack"):
             generator._safe_load_image(BytesIO(b"fake"))

def test_max_pixels_enforcement():
    """Verify MAX_IMAGE_PIXELS is set during execution."""
    generator = ExcelReportGenerator()

    # Reset to None to verify it gets set
    Image.MAX_IMAGE_PIXELS = None

    with patch('src.core.reporting.MatplotlibVisualizer') as MockViz:
         mock_viz_instance = MockViz.return_value
         mock_viz_instance.generate_chart.return_value = BytesIO(b"fake")

         with patch('src.core.reporting.PILImage.open') as mock_open:
             mock_img = MagicMock()
             mock_open.return_value = mock_img

             generator.generate_excel(anomalies_mock, strategy_mock, "test_output.xlsx")

             assert Image.MAX_IMAGE_PIXELS == 50_000_000
