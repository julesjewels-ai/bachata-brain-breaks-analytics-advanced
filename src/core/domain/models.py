"""
Core domain models for the application.
"""
from pydantic import BaseModel, Field, field_validator
import re

class VideoAnalysisInput(BaseModel):
    """
    Schema for video data to be analyzed by the agent.
    Strictly validates input to prevent injection and ensure data integrity.
    """
    video_id: str = Field(..., pattern=r"^vid_\d+$")
    title: str = Field(..., min_length=1, max_length=200)
    views: int = Field(..., ge=0)
    retention_avg_pct: float = Field(..., ge=0.0, le=100.0)
    type: str = Field(..., pattern=r"^(Shorts|Long)$")

    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        # Basic sanitization and prompt injection check
        forbidden_patterns = ["Ignore previous instructions", "System:", "User:"]
        for pattern in forbidden_patterns:
            if pattern in v:
                raise ValueError(f"Potential prompt injection detected: {pattern}")

        # Formula Injection Prevention
        if v.startswith(('=', '@', '+', '-')):
            raise ValueError("Title contains potential Formula Injection (starts with =, @, +, -)")

        # Ensure no control characters
        if not v.isprintable():
            raise ValueError("Title contains non-printable characters")
        return v

class ReportConfig(BaseModel):
    """Configuration for report generation validation."""
    filepath: str = Field(..., description="Path to save the Excel report")

    @field_validator('filepath')
    @classmethod
    def validate_filepath(cls, v: str) -> str:
        if not v.endswith('.xlsx'):
            raise ValueError("File must be an Excel (.xlsx) file")
        if '..' in v:
            raise ValueError("Path traversal detected")
        # Allow slashes for subdirectories, but validate against other injection
        if not re.match(r'^[\w\-. /]+$', v):
            raise ValueError("File path contains invalid characters")
        return v
