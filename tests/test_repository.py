"""
Unit tests for the generic repository pattern.
"""
import json
import pytest
from pydantic import BaseModel

from src.core.repository import JsonlRepository, RepositoryError
from src.core.models import VideoAnalysisInput

class DummyModel(BaseModel):
    id: int
    name: str

def test_jsonl_repository_save(tmp_path):
    """Test saving a generic Pydantic model to a JSONL file."""
    filepath = tmp_path / "test_repo.jsonl"
    repo = JsonlRepository[DummyModel](str(filepath))

    item1 = DummyModel(id=1, name="Test 1")
    item2 = DummyModel(id=2, name="Test 2")

    repo.save(item1)
    repo.save(item2)

    assert filepath.exists()

    with open(filepath, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 2

    loaded1 = json.loads(lines[0])
    assert loaded1["id"] == 1
    assert loaded1["name"] == "Test 1"

    loaded2 = json.loads(lines[1])
    assert loaded2["id"] == 2
    assert loaded2["name"] == "Test 2"

def test_jsonl_repository_save_video_analysis_input(tmp_path):
    """Test saving a domain model to ensure mode='json' behaves correctly."""
    filepath = tmp_path / "test_video_repo.jsonl"
    repo = JsonlRepository[VideoAnalysisInput](str(filepath))

    item = VideoAnalysisInput(
        video_id="vid_123",
        title="Test Video",
        views=1000,
        retention_avg_pct=45.5,
        type="Shorts"
    )

    repo.save(item)

    with open(filepath, 'r') as f:
        data = json.loads(f.read())

    assert data["video_id"] == "vid_123"
    assert data["title"] == "Test Video"
    assert data["views"] == 1000

def test_jsonl_repository_error_handling(tmp_path):
    """Test error handling when file is not writable."""
    # Create a directory with the same name as the target file
    # This will cause an IOError when trying to open it for writing
    filepath = tmp_path / "bad_file.jsonl"
    filepath.mkdir()

    repo = JsonlRepository[DummyModel](str(filepath))
    item = DummyModel(id=1, name="Test Error")

    with pytest.raises(RepositoryError) as exc:
        repo.save(item)

    assert "Persistence error:" in str(exc.value)
