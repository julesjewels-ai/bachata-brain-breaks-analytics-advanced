import pytest
from PIL import Image
from io import BytesIO

def test_decompression_bomb_protection():
    """
    Verify that Pillow raises DecompressionBombError when the image exceeds the pixel limit.
    This ensures that our security hardening strategy (setting MAX_IMAGE_PIXELS) is effective.
    """
    # Create a 100x100 image (10,000 pixels)
    width, height = 100, 100
    img = Image.new('RGB', (width, height), color='red')

    # Save to BytesIO to simulate loading from a file/stream
    img_stream = BytesIO()
    img.save(img_stream, format='PNG')
    img_stream.seek(0)

    # Store original limit to restore later
    original_limit = Image.MAX_IMAGE_PIXELS

    try:
        # Set a limit such that image > 2 * limit to ensure Error, not Warning.
        # Image is 10,000. We need 10,000 > 2 * limit => limit < 5,000.
        # Let's set limit to 2000.
        Image.MAX_IMAGE_PIXELS = 2000

        # Attempt to open should raise DecompressionBombError
        with pytest.raises(Image.DecompressionBombError):
            with Image.open(img_stream) as loaded_img:
                loaded_img.verify() # Trigger the check

    finally:
        # Restore the original limit to avoid affecting other tests
        Image.MAX_IMAGE_PIXELS = original_limit
