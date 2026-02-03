import logging
from typing import List
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from src.core.interfaces import AIService
from src.core.models import VideoAnalysisInput
from src.api.dependencies import get_ai_service

logger = logging.getLogger(__name__)
router = APIRouter()

class AnalysisRequest(BaseModel):
    videos: List[VideoAnalysisInput]

@router.post("/analyze")
def analyze_videos(
    request: AnalysisRequest,
    service: AIService = Depends(get_ai_service)
):
    """
    Synchronous analysis endpoint.
    """
    return {"strategy": service.analyze_semantics(request.videos)}

@router.websocket("/ws/analyze")
async def websocket_analyze(
    websocket: WebSocket,
    service: AIService = Depends(get_ai_service)
):
    """
    WebSocket endpoint for streaming analysis.
    """
    await websocket.accept()
    try:
        # Receive JSON data
        data = await websocket.receive_json()
        # Parse into Pydantic model
        request = AnalysisRequest(**data)

        # Stream response
        async for chunk in service.analyze_stream(request.videos):
            await websocket.send_text(chunk)

    except WebSocketDisconnect:
        logger.debug("WebSocket disconnected client-side")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_text(f"Error: {str(e)}")
        except:
            pass
        await websocket.close()
