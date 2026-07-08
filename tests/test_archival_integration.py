import os
import json
import pytest

from src.core.models import VideoAnalysisInput
from src.core.archival import JSONLRepository, DataArchivalService, ArchivalError


@pytest.fixture
def archival_filepath(tmp_path):
    """Fixture for a temporary archival file path."""
    filepath = tmp_path / "test_archive.jsonl"
    yield str(filepath)
    # Cleanup is handled by tmp_path


@pytest.fixture
def mock_videos():
    """Fixture returning a list of valid VideoAnalysisInput models."""
    return [
        VideoAnalysisInput(
            video_id="vid_001",
            title="Salsa Basic Step",
            views=1000,
            retention_avg_pct=45.5,
            type="Long"
        ),
        VideoAnalysisInput(
            video_id="vid_002",
            title="Sensual Bachata Dip #shorts",
            views=5000,
            retention_avg_pct=85.0,
            type="Shorts"
        )
    ]


@pytest.mark.parametrize("scenario,videos_to_archive", [
    ("multiple_videos", "mock_videos"),
    ("empty_list", []),
])
def test_archival_service_integration(scenario, videos_to_archive, request, archival_filepath):
    """
    Integration test verifying the DataArchivalService successfully persists
    domain models to a JSONL file via JSONLRepository.
    """
    if isinstance(videos_to_archive, str):
        videos = request.getfixturevalue(videos_to_archive)
    else:
        videos = videos_to_archive

    # Setup
    repository = JSONLRepository[VideoAnalysisInput](archival_filepath)
    service = DataArchivalService(repository)

    # Execution
    service.archive_videos(videos)

    # Verification
    assert os.path.exists(archival_filepath)

    with open(archival_filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    assert len(lines) == len(videos), "Number of archived lines should match number of input videos."

    for i, line in enumerate(lines):
        data = json.loads(line)
        original_model = videos[i]

        # Verify strict structural equivalence of the persisted JSON against the Pydantic model
        assert data["video_id"] == original_model.video_id
        assert data["title"] == original_model.title
        assert data["views"] == original_model.views
        assert data["retention_avg_pct"] == original_model.retention_avg_pct
        assert data["type"] == original_model.type


def test_archival_service_raises_on_invalid_path(mock_videos):
    """
    Verifies that the archival service raises an ArchivalError when
    attempting to write to an invalid path.
    """
    # Use a directory path that doesn't exist to force an OSError during open()
    invalid_path = "/path/that/does/not/exist/archive.jsonl"
    repository = JSONLRepository[VideoAnalysisInput](invalid_path)
    service = DataArchivalService(repository)

    with pytest.raises(ArchivalError) as exc_info:
        service.archive_videos(mock_videos)

    assert "Persistence error" in str(exc_info.value)
