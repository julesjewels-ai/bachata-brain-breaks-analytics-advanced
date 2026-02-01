from fastapi import APIRouter, WebSocket, Depends, WebSocketDisconnect
from typing import List
import json
from pydantic import ValidationError
from src.core.services import GeminiStreamingService
from src.core.interfaces import AIService
from src.core.app import VideoAnalysisInput

router = APIRouter()

def get_ai_service() -> AIService:
    """Dependency injection for AI Service."""
    return GeminiStreamingService()

@router.websocket("/ws/generate-strategy")
async def websocket_generate_strategy(
    websocket: WebSocket,
    service: AIService = Depends(get_ai_service)
):
    """
    WebSocket endpoint that accepts a list of videos and streams back the AI strategy analysis.
    """
    await websocket.accept()
    try:
        # Receive data
        data = await websocket.receive_text()

        # Parse and Validate data
        try:
            json_data = json.loads(data)
            if not isinstance(json_data, list):
                await websocket.send_text("Error: Expected a list of video objects.")
                await websocket.close()
                return

            videos = [VideoAnalysisInput(**item) for item in json_data]

        except json.JSONDecodeError:
             await websocket.send_text("Error: Invalid JSON.")
             await websocket.close()
             return
        except ValidationError as e:
             await websocket.send_text(f"Error: Validation failed - {e}")
             await websocket.close()
             return
        except Exception as e:
             await websocket.send_text(f"Error: {str(e)}")
             await websocket.close()
             return

        # Stream response
        async for token in service.analyze_stream(videos):
            await websocket.send_text(token)

        await websocket.close()

    except WebSocketDisconnect:
        # Client disconnected, simple log (or pass)
        pass
