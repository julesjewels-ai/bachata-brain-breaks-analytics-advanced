"""
Integration tests for repository pattern.
"""
import os
import json
import pytest
from src.core.models import VideoAnalysisInput
from src.core.repository import JsonlRepository, RepositoryError

def test_jsonl_repository_saves_model(tmp_path):
    """
    Proves the feature works from "Interface to Implementation".
    """
    # Arrange
    filepath = tmp_path / "test_analysis_inputs.jsonl"
    repo = JsonlRepository[VideoAnalysisInput](str(filepath))

    input_data = {
        "video_id": "vid_123",
        "title": "A Great Bachata Move",
        "views": 1500,
        "retention_avg_pct": 85.5,
        "type": "Shorts"
    }

    # Act
    entity = VideoAnalysisInput(**input_data)
    repo.save(entity)

    # Assert
    assert os.path.exists(str(filepath))
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 1

        saved_dict = json.loads(lines[0])
        assert saved_dict["video_id"] == "vid_123"
        assert saved_dict["title"] == "A Great Bachata Move"
        assert saved_dict["views"] == 1500
        assert saved_dict["retention_avg_pct"] == 85.5
        assert saved_dict["type"] == "Shorts"

def test_jsonl_repository_handles_io_error(tmp_path):
    """
    Proves that RepositoryError is raised gracefully when a file cannot be written to.
    """
    # Arrange
    # Create a directory path, which will raise IOError when trying to open as file
    dirpath = tmp_path / "test_dir"
    os.makedirs(dirpath)

    repo = JsonlRepository[VideoAnalysisInput](str(dirpath))
    entity = VideoAnalysisInput(
        video_id="vid_fail",
        title="Fail",
        views=0,
        retention_avg_pct=0.0,
        type="Long"
    )

    # Act & Assert
    with pytest.raises(RepositoryError):
        repo.save(entity)
