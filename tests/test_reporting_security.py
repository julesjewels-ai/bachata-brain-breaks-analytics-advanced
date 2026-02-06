import unittest.mock as mock
import pandas as pd
from PIL import Image
from src.core.reporting import ExcelReportGenerator
import pytest
import src.core.reporting

def test_pillow_pixel_limit_enforced():
    """Test that Pillow's MAX_IMAGE_PIXELS is set to 50,000,000 to prevent DoS."""
    # This ensures the global constraint is active
    assert Image.MAX_IMAGE_PIXELS == 50_000_000

def test_decompression_bomb_protection():
    """Test that DecompressionBombError is caught and handled gracefully."""
    generator = ExcelReportGenerator()

    # Mock writer
    mock_writer = mock.MagicMock()
    mock_sheet = mock.MagicMock()
    mock_writer.book.create_sheet.return_value = mock_sheet

    # Dummy data
    anomalies = {
        'test': pd.DataFrame({
            'views': [100, 200],
            'retention_avg_pct': [50, 60]
        })
    }

    # Mock MatplotlibVisualizer to return a dummy stream
    with mock.patch('src.core.reporting.MatplotlibVisualizer') as MockViz:
        mock_viz_instance = MockViz.return_value
        mock_viz_instance.generate_chart.return_value = mock.MagicMock()

        # Mock PIL.Image.open to raise DecompressionBombError
        with mock.patch('PIL.Image.open') as mock_open:
            mock_open.side_effect = Image.DecompressionBombError("Decompression Bomb Detected")

            # We also want to ensure that specific logging occurs, but strict assertion on logs
            # might be overkill unless we mock the logger.
            with mock.patch('src.core.reporting.logger') as mock_logger:
                generator._add_visual_insights(mock_writer, anomalies)

                # Check that we didn't crash
                mock_open.assert_called()

                # Verify specific security warning is logged
                # We expect something like logger.warning("Failed to generate visualization: Decompression Bomb Detected")
                # OR if we refactor to catch it specifically, maybe "Security event: ..."
                assert mock_logger.error.called
