from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_analyze_endpoint():
    payload = {
        "videos": [
            {
                "video_id": "vid_1",
                "title": "Bachata Demo",
                "views": 1000,
                "retention_avg_pct": 80.5,
                "type": "Long"
            }
        ]
    }
    response = client.post("/analyze", json=payload)
    assert response.status_code == 200
    assert "strategy" in response.json()
    assert "Analysis Complete" in response.json()["strategy"]

def test_websocket_analyze():
    payload = {
        "videos": [
            {
                "video_id": "vid_1",
                "title": "Bachata Demo",
                "views": 1000,
                "retention_avg_pct": 80.5,
                "type": "Long"
            }
        ]
    }
    with client.websocket_connect("/ws/analyze") as websocket:
        websocket.send_json(payload)
        data = ""
        while True:
            try:
                # receive_text returns the next message
                # if the socket is closed, it might raise or return something else depending on implementation
                # TestClient websocket implementation raises WebSocketDisconnect on close usually,
                # or we just iterate until exception.
                message = websocket.receive_text()
                data += message
            except Exception:
                break

    assert "Analysis Complete" in data
