from typing import List, Optional
from pydantic import BaseModel, Field

class VideoItem(BaseModel):
    """
    Represents a single video's performance data.
    """
    video_id: str = Field(..., description="Unique identifier for the video")
    title: str = Field(..., description="Title of the video")
    views: int = Field(..., ge=0, description="Total views")
    retention_avg_pct: float = Field(..., ge=0.0, le=100.0, description="Average retention percentage")
    type: str = Field(..., description="Type of video (e.g., Shorts, Long)")

class AnalysisRequest(BaseModel):
    """
    Request model for semantic analysis.
    """
    videos: List[VideoItem]

class AnalysisResponse(BaseModel):
    """
    Response model containing the generated strategy.
    """
    strategy: str
