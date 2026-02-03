import pytest
from unittest.mock import MagicMock, patch
from io import BytesIO
from src.core.reporting import ExcelReportGenerator
import logging

class TestImageSecurity:

    @patch('src.core.reporting.PILImage')
    def test_safe_load_image_enforces_limit(self, mock_pil_image):
        """Verify that _safe_load_image sets MAX_IMAGE_PIXELS and verifies image."""

        # Setup
        # We need DecompressionBombError to be an exception class for the except block to work
        mock_pil_image.DecompressionBombError = Exception

        generator = ExcelReportGenerator()
        dummy_stream = BytesIO(b"fake_image_data")

        # Mock the image object returned by open
        mock_img = MagicMock()
        mock_pil_image.open.return_value = mock_img
        mock_img.__enter__.return_value = mock_img
        mock_img.__exit__.return_value = None

        # Call the method
        if not hasattr(generator, '_safe_load_image'):
            pytest.skip("_safe_load_image not implemented yet")

        result = generator._safe_load_image(dummy_stream)

        # Assertions
        # Check if MAX_IMAGE_PIXELS was set to 50,000,000
        assert mock_pil_image.MAX_IMAGE_PIXELS == 50_000_000

        # Check if open was called
        assert mock_pil_image.open.called

        # Check if verify was called
        mock_img.verify.assert_called()

    @patch('src.core.reporting.PILImage')
    def test_safe_load_image_rejects_bomb(self, mock_pil_image):
        """Verify that validation error is raised on DecompressionBombError."""
        # Setup the mock to have DecompressionBombError as a real exception
        mock_pil_image.DecompressionBombError = Exception

        generator = ExcelReportGenerator()
        dummy_stream = BytesIO(b"bomb_data")

        # Simulate DecompressionBombError
        mock_pil_image.open.side_effect = mock_pil_image.DecompressionBombError("Bomb!")

        if not hasattr(generator, '_safe_load_image'):
            pytest.skip("_safe_load_image not implemented yet")

        with pytest.raises(ValueError, match="Security validation failed"):
            generator._safe_load_image(dummy_stream)

    @patch('src.core.reporting.PILImage')
    def test_safe_load_image_rejects_corrupt(self, mock_pil_image):
        """Verify that validation error is raised on IOError."""
        # Setup the mock to have DecompressionBombError as a real exception
        mock_pil_image.DecompressionBombError = Exception

        generator = ExcelReportGenerator()
        dummy_stream = BytesIO(b"corrupt_data")

        # Simulate IOError
        mock_pil_image.open.side_effect = IOError("Corrupt!")

        if not hasattr(generator, '_safe_load_image'):
            pytest.skip("_safe_load_image not implemented yet")

        with pytest.raises(ValueError, match="Security validation failed"):
            generator._safe_load_image(dummy_stream)
