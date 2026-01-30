import pytest
from fastapi.testclient import TestClient
from src.api.main import app
from src.core.domain import VideoAnalysisInput

client = TestClient(app)

def test_websocket_streaming_analysis():
    """
    Verifies that the WebSocket endpoint accepts a valid payload and streams a response.
    """
    video_data = {
        "videos": [
            {
                "video_id": "vid_101",
                "title": "Bachata Sensual Basic",
                "views": 1500,
                "retention_avg_pct": 85.5,
                "type": "Long"
            }
        ]
    }

    with client.websocket_connect("/ws/analyze") as websocket:
        websocket.send_json(video_data)

        # Accumulate the streamed response
        response_text = ""
        while True:
            data = websocket.receive_text()
            if data == "\n[END OF TRANSMISSION]":
                break
            response_text += data

        # Verify content
        assert "[Gemini 3 Thinking Mode]" in response_text
        assert "Pattern Identification" in response_text
        assert "Analysis Complete" in response_text

def test_websocket_invalid_input():
    """
    Verifies error handling for invalid input.
    """
    invalid_data = {
        "videos": [
            {
                "video_id": "bad_id", # Invalid ID format
                "title": "Test",
                "views": -1, # Invalid views
                "retention_avg_pct": 50.0,
                "type": "Long"
            }
        ]
    }

    with client.websocket_connect("/ws/analyze") as websocket:
        websocket.send_json(invalid_data)
        data = websocket.receive_text()
        assert "Error: Invalid data format" in data
