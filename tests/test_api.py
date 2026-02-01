import pytest
from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Bachata Brain Breaks Analytics API. Connect to /ws/generate-strategy for streaming analysis."}

def test_websocket_streaming():
    # Prepare valid data
    videos = [
        {
            "video_id": "vid_1",
            "title": "Bachata Basic Step",
            "views": 1000,
            "retention_avg_pct": 50.5,
            "type": "Long"
        }
    ]

    with client.websocket_connect("/ws/generate-strategy") as websocket:
        websocket.send_json(videos)

        # Check first message (Thinking Mode Initiated)
        data = websocket.receive_text()
        assert "[Gemini 3 Thinking Mode] Analysis Initiated" in data

        # We can consume the rest
        messages = [data]
        try:
            while True:
                # receive_text raises WebSocketDisconnect when closed if using some clients,
                # but TestClient might handle it differently.
                # Starlette TestClient raises WebSocketDisconnect.
                msg = websocket.receive_text()
                messages.append(msg)
        except Exception:
            pass

        assert len(messages) > 1
        assert "Analysis Complete." in messages[-1]

def test_websocket_invalid_input():
    with client.websocket_connect("/ws/generate-strategy") as websocket:
        websocket.send_text("Not JSON")
        data = websocket.receive_text()
        assert "Error: Invalid JSON" in data

def test_websocket_validation_error():
    invalid_videos = [
        {
            "video_id": "bad_id", # Wrong pattern, expects vid_...
            "title": "Title",
            "views": 100,
            "retention_avg_pct": 50.0,
            "type": "Long"
        }
    ]
    with client.websocket_connect("/ws/generate-strategy") as websocket:
        websocket.send_json(invalid_videos)
        data = websocket.receive_text()
        assert "Error: Validation failed" in data
