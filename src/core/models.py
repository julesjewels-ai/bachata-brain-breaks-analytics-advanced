"""
Domain models for Bachata Brain Breaks Analytics.
"""
from typing import Any
from pydantic import BaseModel, Field, field_validator

class CacheEntry(BaseModel):
    """
    Schema for cached data.
    """
    key: str = Field(..., description="Unique cache key")
    value: Any = Field(..., description="Cached value")
    expires_at: float = Field(..., description="Timestamp when the entry expires")

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
