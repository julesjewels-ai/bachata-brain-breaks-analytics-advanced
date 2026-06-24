import os
import json
from unittest.mock import patch
import pytest

from src.core.models import VideoAnalysisInput
from src.core.repository import JsonlRepository, RepositoryError

def test_jsonl_repository_integration(tmp_path):
    """
    Integration test for JsonlRepository saving and restoring data.
    """
    file_path = tmp_path / "test_archive.jsonl"
    repo = JsonlRepository[VideoAnalysisInput](str(file_path))

    inputs = [
        VideoAnalysisInput(
            video_id="id1",
            title="Video 1",
            views=1000,
            retention_avg_pct=50.5,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="id2",
            title="Video 2",
            views=2000,
            retention_avg_pct=60.0,
            type="Long"
        )
    ]

    # Save the items
    repo.save_all(inputs)

    # Verify the file exists
    assert file_path.exists()

    # Read back the items
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 2

    loaded_item_1 = VideoAnalysisInput(**json.loads(lines[0]))
    assert loaded_item_1.video_id == "id1"
    assert loaded_item_1.title == "Video 1"

    loaded_item_2 = VideoAnalysisInput(**json.loads(lines[1]))
    assert loaded_item_2.video_id == "id2"
    assert loaded_item_2.title == "Video 2"


def test_jsonl_repository_error_handling(tmp_path):
    """
    Verifies that RepositoryError is raised on file IO failure.
    """
    # Use a directory path instead of a file to force an IOError
    repo = JsonlRepository[VideoAnalysisInput](str(tmp_path))

    inputs = [
        VideoAnalysisInput(
            video_id="id1",
            title="Video 1",
            views=1000,
            retention_avg_pct=50.5,
            type="Shorts"
        )
    ]

    with pytest.raises(RepositoryError) as exc_info:
        repo.save_all(inputs)

    assert "Persistence error" in str(exc_info.value)
