"""
Integration tests for the JsonlRepository and domain object archiving.
"""
import os
import json
import pytest
from pydantic import ValidationError

from src.core.models import VideoAnalysisInput
from src.core.repository import JsonlRepository


@pytest.fixture
def temp_jsonl_file(tmp_path):
    filepath = tmp_path / "test_archive.jsonl"
    yield str(filepath)
    if filepath.exists():
        filepath.unlink()


@pytest.mark.parametrize("inputs", [
    (
        [
            VideoAnalysisInput(
                video_id="vid-1", title="Test Title", views=1000,
                retention_avg_pct=50.0, type="Shorts"
            )
        ]
    ),
    (
        [
            VideoAnalysisInput(
                video_id="vid-1", title="Test Title", views=1000,
                retention_avg_pct=50.0, type="Shorts"
            ),
            VideoAnalysisInput(
                video_id="vid-2", title="Long Video", views=5000,
                retention_avg_pct=75.5, type="Long"
            )
        ]
    )
])
def test_jsonl_repository_save_all(temp_jsonl_file, inputs):
    """Test that JsonlRepository correctly serializes and saves sequences."""
    repo = JsonlRepository[VideoAnalysisInput](temp_jsonl_file)

    repo.save_all(inputs)

    with open(temp_jsonl_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == len(inputs), f"Expected {len(inputs)} lines, got {len(lines)}"

    for i, line in enumerate(lines):
        data = json.loads(line)
        assert data["video_id"] == inputs[i].video_id
        assert data["title"] == inputs[i].title
        assert data["views"] == inputs[i].views
        assert data["retention_avg_pct"] == inputs[i].retention_avg_pct
        assert data["type"] == inputs[i].type


def test_jsonl_repository_save(temp_jsonl_file):
    """Test that JsonlRepository correctly serializes and saves single item."""
    repo = JsonlRepository[VideoAnalysisInput](temp_jsonl_file)

    item = VideoAnalysisInput(
        video_id="vid-1", title="Test Title", views=1000,
        retention_avg_pct=50.0, type="Shorts"
    )

    repo.save(item)

    with open(temp_jsonl_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 1

    data = json.loads(lines[0])
    assert data["video_id"] == item.video_id
    assert data["title"] == item.title
    assert data["views"] == item.views
    assert data["retention_avg_pct"] == item.retention_avg_pct
    assert data["type"] == item.type
