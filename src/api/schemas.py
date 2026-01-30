from typing import List
from pydantic import BaseModel
from src.core.domain import VideoAnalysisInput

class AnalysisRequest(BaseModel):
    """
    Request model for analysis.
    """
    videos: List[VideoAnalysisInput]
