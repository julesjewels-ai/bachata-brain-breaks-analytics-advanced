import io
import pytest
from PIL import Image
from src.core.reporting import ExcelReportGenerator

def test_safe_load_image_sets_limit():
    """Test that safe_load_image sets the secure pixel limit."""
    img = Image.new('RGB', (10, 10), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    # Reset to something else to verify it gets updated
    Image.MAX_IMAGE_PIXELS = 1000

    ExcelReportGenerator._safe_load_image(buf)

    # Verify it was updated to the secure limit (50M)
    assert Image.MAX_IMAGE_PIXELS == 50_000_000

def test_safe_load_image_handles_large_image_error():
    """Test that safe_load_image raises ValueError on DecompressionBombError."""
    # We simulate DecompressionBombError by mocking Image.open

    buf = io.BytesIO(b"fake data")

    from PIL import Image as PILImage

    # Store original
    original_open = PILImage.open

    def mock_open(*args, **kwargs):
        raise PILImage.DecompressionBombError("Image too large")

    try:
        PILImage.open = mock_open
        with pytest.raises(ValueError, match="Invalid image"):
            ExcelReportGenerator._safe_load_image(buf)
    finally:
        PILImage.open = original_open

def test_safe_load_image_valid_execution():
    """Test that safe_load_image processes a valid image correctly."""
    img = Image.new('RGB', (20, 20), color='green')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)

    result = ExcelReportGenerator._safe_load_image(buf)

    assert isinstance(result, Image.Image)
    assert result.width == 20
    assert result.height == 20
