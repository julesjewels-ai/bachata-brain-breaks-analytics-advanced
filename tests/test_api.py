from fastapi.testclient import TestClient
from src.api.main import app
from src.api.routes import get_ai_service
from src.core.interfaces import AIService
from typing import List, Dict, Any, AsyncGenerator
import pytest

class MockAIService:
    def analyze_semantics(self, videos: List[Dict[str, Any]]) -> str:
        return "Test Strategy"

    async def analyze_stream(self, videos: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
        yield "Test "
        yield "Streaming"

client = TestClient(app)

def override_get_ai_service():
    return MockAIService()

app.dependency_overrides[get_ai_service] = override_get_ai_service

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Bachata Analytics API is running. Documentation at /docs"}

def test_analyze_endpoint():
    payload = {
        "videos": [
            {
                "video_id": "vid_1",
                "title": "Test Video",
                "views": 1000,
                "retention_avg_pct": 50.0,
                "type": "Long"
            }
        ]
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    assert response.json()["strategy"] == "Test Strategy"

@pytest.mark.anyio
def test_websocket_endpoint():
    # WebSocket testing usually requires the 'httpx' or 'starlette' TestClient
    # but fastapi.testclient.TestClient (wrapping Starlette) supports websocket_connect
    # if httpx is installed.
    # Note: websocket_connect is synchronous in TestClient unless using AsyncClient.
    # But TestClient manages the event loop for the app.

    with client.websocket_connect("/ws/analyze") as websocket:
        payload = {
            "videos": [
                {
                    "video_id": "vid_1",
                    "title": "Test Video",
                    "views": 1000,
                    "retention_avg_pct": 50.0,
                    "type": "Long"
                }
            ]
        }
        websocket.send_json(payload)
        data = websocket.receive_text()
        assert data == "Test "
        data = websocket.receive_text()
        assert data == "Streaming"
