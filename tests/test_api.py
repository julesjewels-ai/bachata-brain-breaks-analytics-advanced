from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_analyze_endpoint():
    response = client.post("/api/v1/analyze")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "anomalies_count" in data
    assert "strategy" in data
    assert data["message"] == "Analysis complete"

def test_report_endpoint():
    # Helper to mock file generation or ensure path is writable is not strictly needed
    # as the service generates in current directory which is writable in sandbox.
    # However, to avoid creating files during tests, we might want to mock.
    # But integration test is fine here.
    response = client.post("/api/v1/report")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
