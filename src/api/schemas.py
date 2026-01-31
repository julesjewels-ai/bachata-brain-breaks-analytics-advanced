from typing import List
from pydantic import BaseModel
from src.core.domain import VideoAnalysisInput

class AnalysisRequest(BaseModel):
    videos: List[VideoAnalysisInput]

class AnalysisResponse(BaseModel):
    strategy: str
