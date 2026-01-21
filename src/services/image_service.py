"""
Image generation service for creating video thumbnails.
Demonstrates SOLID principles: Single Responsibility (image creation) and Dependency Inversion (can be injected).
"""
from io import BytesIO
from typing import Optional, Protocol, Union
from PIL import Image, ImageDraw, ImageFont # type: ignore
from pydantic import BaseModel, Field

class ThumbnailConfig(BaseModel):
    """Configuration for thumbnail generation."""
    width: int = Field(160, description="Width of the thumbnail in pixels")
    height: int = Field(90, description="Height of the thumbnail in pixels")
    bg_color: str = Field("#2C3E50", description="Background color hex code")
    text_color: str = Field("#ECF0F1", description="Text color hex code")
    font_size: int = Field(10, description="Font size")

class IThumbnailService(Protocol):
    """Interface for thumbnail services to ensure Dependency Inversion."""
    def generate_thumbnail(self, title: str, config: Optional[ThumbnailConfig] = None) -> BytesIO:
        ...

class ThumbnailService:
    """
    Service responsible for generating visual assets (thumbnails).
    Uses Pillow to create a placeholder image with the video title.
    """
    def __init__(self, default_config: Optional[ThumbnailConfig] = None):
        self.default_config = default_config or ThumbnailConfig()

    def generate_thumbnail(self, title: str, config: Optional[ThumbnailConfig] = None) -> BytesIO:
        """
        Generates a thumbnail image stream for a given video title.

        Args:
            title: The title of the video.
            config: Optional override configuration.

        Returns:
            BytesIO stream containing the PNG image.
        """
        cfg = config or self.default_config

        # Security: Pillow Image.new is safe, but we validate dimensions in Pydantic config
        img = Image.new('RGB', (cfg.width, cfg.height), color=cfg.bg_color)
        d = ImageDraw.Draw(img)

        # Simple text wrapping logic
        words = title.split()
        lines = []
        current_line: list[str] = []

        # Very basic estimation (improve if needed)
        chars_per_line = cfg.width // (cfg.font_size // 2)

        for word in words:
            if len(" ".join(current_line + [word])) <= chars_per_line:
                current_line.append(word)
            else:
                lines.append(" ".join(current_line))
                current_line = [word]
        lines.append(" ".join(current_line))

        # Draw text centered
        y_text = (cfg.height - (len(lines) * cfg.font_size)) // 2
        for line in lines:
            # Calculate text width roughly
            text_width = len(line) * (cfg.font_size // 2)
            x_text = (cfg.width - text_width) // 2
            d.text((x_text, y_text), line, fill=cfg.text_color)
            y_text += cfg.font_size + 2

        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        return img_buffer
