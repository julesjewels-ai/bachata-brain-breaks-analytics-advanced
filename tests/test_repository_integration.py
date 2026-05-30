import json
import os
from src.core.repository import JsonlRepository
from src.core.models import VideoAnalysisInput

def test_jsonl_repository_save_all(tmp_path):
    # Setup
    test_file = tmp_path / "test_archive.jsonl"
    repo = JsonlRepository[VideoAnalysisInput](str(test_file))

    # Create test data
    inputs = [
        VideoAnalysisInput(
            video_id="vid1", title="Test 1", views=100, retention_avg_pct=50.0, type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="vid2", title="Test 2", views=200, retention_avg_pct=60.0, type="Long"
        )
    ]

    # Execute
    repo.save_all(inputs)

    # Verify
    assert os.path.exists(test_file)
    with open(test_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    assert len(lines) == 2

    # Read back and verify first record
    data1 = json.loads(lines[0])
    assert data1["video_id"] == "vid1"
    assert data1["title"] == "Test 1"
    assert data1["views"] == 100
    assert data1["retention_avg_pct"] == 50.0
    assert data1["type"] == "Shorts"

    # Read back and verify second record
    data2 = json.loads(lines[1])
    assert data2["video_id"] == "vid2"
    assert data2["type"] == "Long"
