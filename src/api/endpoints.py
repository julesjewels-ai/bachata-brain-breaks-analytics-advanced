from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from src.api.schemas import AnalysisRequest
from src.api.dependencies import get_ai_service
from src.core.services.ai import AIService
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/analyze")
async def websocket_analyze(
    websocket: WebSocket,
    service: AIService = Depends(get_ai_service)
):
    """
    WebSocket endpoint for streaming AI analysis.
    Clients send a JSON payload matching AnalysisRequest.
    Server streams back text chunks.
    """
    await websocket.accept()

    try:
        while True:
            # Receive JSON data
            data = await websocket.receive_json()

            # Validate using Pydantic
            try:
                request = AnalysisRequest(**data)
            except Exception as e:
                await websocket.send_text(f"Error: Invalid data format. {str(e)}")
                continue

            # Stream response
            async for chunk in service.analyze_stream(request.videos):
                await websocket.send_text(chunk)

            # Signal completion (optional, or just close connection,
            # but usually we keep it open for next request)
            await websocket.send_text("\n[END OF TRANSMISSION]")

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011) # Internal Error
        except:
            pass
