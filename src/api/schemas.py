from pydantic import BaseModel
from typing import Dict

class AnalysisResponse(BaseModel):
    message: str
    anomalies_count: Dict[str, int]
    strategy: str
