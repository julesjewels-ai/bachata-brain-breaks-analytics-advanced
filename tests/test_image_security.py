import unittest
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image
from src.core.reporting import ExcelReportGenerator

class TestImageSecurity(unittest.TestCase):
    def test_safe_load_image_valid(self):
        """Test that a valid, small image loads correctly."""
        # Create a small valid image
        img = Image.new('RGB', (100, 100), color='red')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)

        loaded_img = ExcelReportGenerator._safe_load_image(buf)

        self.assertIsInstance(loaded_img, Image.Image)
        self.assertEqual(loaded_img.size, (100, 100))

    @patch('src.core.reporting.PILImage.open')
    def test_safe_load_image_bomb(self, mock_open):
        """Test that a DecompressionBombError is caught and raised as ValueError."""
        # Setup the mock to raise DecompressionBombError
        # Use the actual exception class from the module if possible, or PIL.Image
        mock_open.side_effect = Image.DecompressionBombError("Image too large")

        buf = BytesIO(b"fake data")

        with self.assertRaises(ValueError) as cm:
            ExcelReportGenerator._safe_load_image(buf)

        self.assertIn("Invalid or unsafe image", str(cm.exception))

    @patch('src.core.reporting.PILImage.open')
    def test_safe_load_image_io_error(self, mock_open):
        """Test that generic IOError is caught."""
        mock_open.side_effect = IOError("Corrupt file")

        buf = BytesIO(b"fake data")

        with self.assertRaises(ValueError) as cm:
            ExcelReportGenerator._safe_load_image(buf)

        self.assertIn("Invalid or unsafe image", str(cm.exception))
