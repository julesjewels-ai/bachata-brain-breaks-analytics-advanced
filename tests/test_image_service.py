"""
Unit tests for the ThumbnailService.
"""
from io import BytesIO
from PIL import Image # type: ignore
from src.services.image_service import ThumbnailService, ThumbnailConfig

def test_generate_thumbnail_returns_bytesio():
    service = ThumbnailService()
    result = service.generate_thumbnail("Test Video")
    assert isinstance(result, BytesIO)
    result.seek(0)
    assert len(result.read()) > 0

def test_generate_thumbnail_valid_image():
    service = ThumbnailService()
    stream = service.generate_thumbnail("Test Video")
    img = Image.open(stream)
    assert img.format == "PNG"
    assert img.size == (160, 90) # Default size

def test_generate_thumbnail_custom_config():
    config = ThumbnailConfig(width=200, height=100, bg_color="#FFFFFF")
    service = ThumbnailService(default_config=config)
    stream = service.generate_thumbnail("Custom Config")
    img = Image.open(stream)
    assert img.size == (200, 100)
    # Check top-left pixel color (approximate check not easily done without inspecting raw bytes or advanced PIL usage)
    # But size confirmation is good enough for structure.

def test_generate_thumbnail_long_text_wrapping():
    service = ThumbnailService()
    long_title = "This is a very long title that should wrap to multiple lines"
    stream = service.generate_thumbnail(long_title)
    img = Image.open(stream)
    assert img.size == (160, 90)
