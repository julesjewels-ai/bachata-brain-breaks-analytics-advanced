from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from pydantic import ValidationError
from src.api.schemas import AnalysisRequest, AnalysisResponse
from src.core.services.ai import GeminiStreamingService
from src.core.interfaces import AIService

router = APIRouter()

# Dependency Injection for Service
def get_ai_service() -> AIService:
    return GeminiStreamingService()

@router.post("/analyze", response_model=AnalysisResponse)
def analyze_videos(
    request: AnalysisRequest,
    service: AIService = Depends(get_ai_service)
):
    """
    Synchronous analysis endpoint.
    """
    try:
        strategy = service.analyze_semantics(request.videos)
        return AnalysisResponse(strategy=strategy)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
        # Receive JSON data matching AnalysisRequest
        data = await websocket.receive_json()
        try:
            request = AnalysisRequest(**data)
        except ValidationError as e:
            await websocket.send_text(f"Validation Error: {e}")
            await websocket.close(code=1008)
            return

        # Stream response
        async for token in service.analyze_stream(request.videos):
            await websocket.send_text(token)

        await websocket.close()
    except WebSocketDisconnect:
        # Client disconnected normally
        pass
    except Exception as e:
        # Check if connection is still open before sending
        try:
            await websocket.send_text(f"Error: {str(e)}")
            await websocket.close(code=1011)
        except:
            pass
