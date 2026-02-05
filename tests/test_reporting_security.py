import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from PIL import Image
from src.core.reporting import ExcelReportGenerator

class TestReportingSecurity:

    @patch('src.core.reporting.PILImage')
    @patch('src.core.reporting.XLImage')
    @patch('src.core.reporting.MatplotlibVisualizer')
    def test_add_visual_insights_sets_pixel_limit(self, mock_viz, mock_xl_img, mock_pil_img):
        """Verify that processing images sets a safe pixel limit."""
        # Setup
        generator = ExcelReportGenerator()
        mock_writer = MagicMock()
        mock_writer.book.create_sheet.return_value = MagicMock()

        # Mock anomalies data
        anomalies = {
            'Test': pd.DataFrame({'views': [100], 'retention_avg_pct': [50.0]})
        }

        # Setup mock behavior
        mock_viz_instance = mock_viz.return_value
        mock_viz_instance.generate_chart.return_value = b'fake_image_data'

        # Mock PIL Image open
        mock_img_obj = MagicMock()
        mock_pil_img.open.return_value = mock_img_obj

        # Execute
        generator._add_visual_insights(mock_writer, anomalies)

        # Verify MAX_IMAGE_PIXELS was set to 50,000,000
        assert mock_pil_img.MAX_IMAGE_PIXELS == 50_000_000

    @patch('src.core.reporting.PILImage')
    @patch('src.core.reporting.MatplotlibVisualizer')
    def test_add_visual_insights_handles_decompression_bomb(self, mock_viz, mock_pil_img):
        """Verify that DecompressionBombError is caught gracefully."""
        # Setup
        generator = ExcelReportGenerator()
        mock_writer = MagicMock()

        anomalies = {
            'Test': pd.DataFrame({'views': [100], 'retention_avg_pct': [50.0]})
        }

        mock_viz_instance = mock_viz.return_value
        mock_viz_instance.generate_chart.return_value = b'fake_image_data'

        # Configure the mock to have the exception class
        # This is critical because the code will catch PILImage.DecompressionBombError
        # When patched, PILImage is a mock, so PILImage.DecompressionBombError is a mock.
        # We need to make sure the side_effect raises something that matches the caught exception.

        # Real exception class
        real_exception = Image.DecompressionBombError
        mock_pil_img.DecompressionBombError = real_exception
        mock_pil_img.open.side_effect = real_exception("Decompression Bomb detected!")

        # Execute - should not raise exception (swallowed by logger.warning)
        try:
            generator._add_visual_insights(mock_writer, anomalies)
        except Exception as e:
            pytest.fail(f"Exception was not caught: {e}")

        # Verify it was called
        mock_pil_img.open.assert_called_once()
