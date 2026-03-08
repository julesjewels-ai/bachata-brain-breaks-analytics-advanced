import pytest
import json
from src.core.models import VideoAnalysisInput
from src.core.repository import JsonlRepository, RepositoryError

@pytest.fixture
def temp_repo_file(tmp_path):
    filepath = tmp_path / "test_repo.jsonl"
    yield str(filepath)
    if filepath.exists():
        filepath.unlink()

@pytest.fixture
def sample_videos():
    return [
        VideoAnalysisInput(
            video_id="test1",
            title="Bachata Test Title 1",
            views=1000,
            retention_avg_pct=50.5,
            type="Shorts"
        ),
        VideoAnalysisInput(
            video_id="test2",
            title="Bachata Test Title 2",
            views=2000,
            retention_avg_pct=75.0,
            type="Long"
        )
    ]

def test_jsonl_repository_save_and_get_all(temp_repo_file, sample_videos):
    repo = JsonlRepository(filepath=temp_repo_file, model_cls=VideoAnalysisInput)

    # Save a single entity
    repo.save(sample_videos[0])

    # Verify file contents directly
    with open(temp_repo_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["video_id"] == "test1"
        assert data["title"] == "Bachata Test Title 1"

    # Get all entities
    results = repo.get_all()
    assert len(results) == 1
    assert results[0].video_id == "test1"

def test_jsonl_repository_save_all(temp_repo_file, sample_videos):
    repo = JsonlRepository(filepath=temp_repo_file, model_cls=VideoAnalysisInput)

    # Save all entities
    repo.save_all(sample_videos)

    # Get all entities
    results = repo.get_all()
    assert len(results) == 2
    assert results[0].video_id == "test1"
    assert results[1].video_id == "test2"

def test_jsonl_repository_empty_file(temp_repo_file):
    repo = JsonlRepository(filepath=temp_repo_file, model_cls=VideoAnalysisInput)
    results = repo.get_all()
    assert results == []

def test_jsonl_repository_invalid_path(sample_videos):
    # Using a directory as a file path should raise RepositoryError
    repo = JsonlRepository(filepath="/", model_cls=VideoAnalysisInput)

    with pytest.raises(RepositoryError, match="Persistence error"):
        repo.save(sample_videos[0])

    with pytest.raises(RepositoryError, match="Persistence error"):
        repo.save_all(sample_videos)

    with pytest.raises(RepositoryError, match="Read error"):
        repo.get_all()
