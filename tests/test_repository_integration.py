import os
import json
from src.core.repository import JsonlRepository
from src.core.models import VideoAnalysisInput


def test_jsonl_repository_integration(tmp_path):
    """
    Test that JsonlRepository correctly persists a sequence of
    VideoAnalysisInput instances to a JSONL file, and the contents
    can be parsed back properly matching the input.
    """
    filepath = os.path.join(tmp_path, "test_archive.jsonl")
    repository = JsonlRepository[VideoAnalysisInput](filepath=filepath)

    inputs = [
        VideoAnalysisInput(
            video_id="vid_1",
            title="Test Video 1",
            views=1000,
            retention_avg_pct=45.5,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="vid_2",
            title="Test Video 2",
            views=5000,
            retention_avg_pct=60.0,
            type="Long"
        )
    ]

    # Act
    repository.save_all(inputs)

    # Assert
    assert os.path.exists(filepath)
    with open(filepath, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 2

        data1 = json.loads(lines[0])
        assert data1['video_id'] == "vid_1"
        assert data1['title'] == "Test Video 1"
        assert data1['views'] == 1000
        assert data1['retention_avg_pct'] == 45.5
        assert data1['type'] == "Shorts"

        data2 = json.loads(lines[1])
        assert data2['video_id'] == "vid_2"
        assert data2['title'] == "Test Video 2"
        assert data2['views'] == 5000
        assert data2['retention_avg_pct'] == 60.0
        assert data2['type'] == "Long"
