import io
import pytest
from unittest.mock import MagicMock, patch
from PIL import Image
from src.core.reporting import ExcelReportGenerator

class TestImageSecurity:

    def test_safe_load_image_valid(self):
        """Test that safe_load_image accepts a valid small image."""
        # Create a small valid image (10x10 = 100 pixels)
        img = Image.new('RGB', (10, 10), color='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        generator = ExcelReportGenerator()
        # Accessing private method for testing purpose
        # Note: This test assumes the method exists. It will fail until implemented.
        loaded_img = generator._safe_load_image(buf)

        assert loaded_img is not None
        assert loaded_img.format == 'PNG'
        assert loaded_img.size == (10, 10)

    def test_safe_load_image_decompression_bomb_handling(self):
        """Test that safe_load_image handles DecompressionBombError gracefully."""
        buf = io.BytesIO(b"fake image data")
        generator = ExcelReportGenerator()

        # Mock PILImage.open to raise DecompressionBombError
        with patch('src.core.reporting.PILImage.open') as mock_open:
            mock_open.side_effect = Image.DecompressionBombError("Image is too large")

            with pytest.raises(RuntimeError, match="Image file processing attempt failed"):
                 generator._safe_load_image(buf)

    def test_safe_load_image_invalid_file(self):
        """Test that safe_load_image rejects non-image data."""
        buf = io.BytesIO(b"Not an image")
        generator = ExcelReportGenerator()

        with pytest.raises(RuntimeError, match="Image file processing attempt failed"):
            generator._safe_load_image(buf)

    def test_max_pixels_enforced(self):
         """Verify that MAX_IMAGE_PIXELS is set to 50,000,000."""
         img = Image.new('RGB', (10, 10), color='green')
         buf = io.BytesIO()
         img.save(buf, format='PNG')
         buf.seek(0)

         generator = ExcelReportGenerator()
         generator._safe_load_image(buf)

         assert Image.MAX_IMAGE_PIXELS == 50_000_000
