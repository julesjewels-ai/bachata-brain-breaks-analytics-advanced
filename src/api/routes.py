from functools import lru_cache
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from src.api.schemas import AnalysisRequest, AnalysisResponse
from src.core.interfaces import AIService
from src.core.ai import GeminiService

router = APIRouter()

@lru_cache
def get_ai_service() -> AIService:
    """Dependency provider for AIService. Cached to reuse the service instance."""
    return GeminiService()

@router.post("/analyze", response_model=AnalysisResponse)
def analyze_videos(request: AnalysisRequest, service: AIService = Depends(get_ai_service)):
    """
    Synchronous endpoint to analyze video performance and generate a strategy.

    Note: This is defined as a sync function (def) so FastAPI runs it in a threadpool,
    preventing the blocking internal API call from freezing the event loop.
    """
    # Convert Pydantic models to list of dicts for the service
    videos_data = [v.model_dump() for v in request.videos]
    strategy = service.analyze_semantics(videos_data)
    return AnalysisResponse(strategy=strategy)

@router.websocket("/ws/analyze")
async def websocket_analyze(websocket: WebSocket, service: AIService = Depends(get_ai_service)):
    """
    WebSocket endpoint for streaming analysis.
    """
    await websocket.accept()
    try:
        # Expect JSON data matching AnalysisRequest
        data = await websocket.receive_json()
        request = AnalysisRequest(**data)
        videos_data = [v.model_dump() for v in request.videos]

        async for token in service.analyze_stream(videos_data):
            await websocket.send_text(token)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(f"Error: {e}")
        await websocket.close()
