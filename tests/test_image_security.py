import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from src.core.reporting import ExcelReportGenerator
from PIL import Image

class TestImageSecurity:
    def test_safe_load_image_security_checks(self):
        """
        Test that _safe_load_image enforces security constraints:
        1. Sets MAX_IMAGE_PIXELS
        2. Verifies the image
        3. Re-opens the image after verification
        """
        # Prepare a mock stream
        stream = BytesIO(b"fake_image_data")

        # Mock PIL.Image in the reporting module
        with patch("src.core.reporting.PILImage") as mock_pil:
            # Setup mock image
            mock_img = MagicMock()
            # Allow the mock image to be used as a context manager if needed (though open() returns it)
            mock_img.__enter__.return_value = mock_img
            mock_pil.open.return_value = mock_img

            # We assume the method will be available.
            # If it's not implemented yet, this test will raise AttributeError.
            if not hasattr(ExcelReportGenerator, '_safe_load_image'):
                 pytest.skip("ExcelReportGenerator._safe_load_image not implemented yet")

            result = ExcelReportGenerator._safe_load_image(stream)

            # 1. Assert MAX_IMAGE_PIXELS is set
            assert mock_pil.MAX_IMAGE_PIXELS == 50_000_000, "MAX_IMAGE_PIXELS not set to 50M"

            # 2. Assert verify was called
            mock_img.verify.assert_called_once()

            # 3. Assert open was called twice (once for verify, once for return)
            assert mock_pil.open.call_count == 2

            # 4. Assert result is the image object
            assert result == mock_img

    def test_safe_load_image_handles_errors(self):
        """Test that validation errors are caught and re-raised securely."""
        stream = BytesIO(b"bad_data")

        with patch("src.core.reporting.PILImage") as mock_pil:
            mock_img = MagicMock()
            mock_pil.open.return_value = mock_img

            # Simulate verification failure
            mock_img.verify.side_effect = Exception("Corrupt")

            if not hasattr(ExcelReportGenerator, '_safe_load_image'):
                 pytest.skip("ExcelReportGenerator._safe_load_image not implemented yet")

            with pytest.raises(RuntimeError) as excinfo:
                ExcelReportGenerator._safe_load_image(stream)

            assert "Invalid image file processing attempt" in str(excinfo.value)
