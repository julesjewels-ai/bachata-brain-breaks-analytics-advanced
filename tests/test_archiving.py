"""
Tests for the archiving module.
"""
import os
import pytest
import pandas as pd
from unittest.mock import AsyncMock, Mock, ANY
from src.core.archiving import ArchivingDataIngestionService, JsonlVideoRepository, ArchivingError
from src.core.interfaces import DataIngestionService
from src.core.models import VideoAnalysisInput


@pytest.fixture
def temp_archive_file(tmp_path):
    """Fixture providing a temporary filepath for JSONL archive."""
    return str(tmp_path / "test_archive.jsonl")


@pytest.mark.asyncio
async def test_archiving_data_ingestion_service(temp_archive_file: str) -> None:
    """
    Tests that ArchivingDataIngestionService correctly wraps an inner service,
    persists data via JsonlVideoRepository, and returns the original DataFrame.
    """
    # 1. Setup inner mock service
    mock_inner_service = AsyncMock(spec=DataIngestionService)

    # Create test data that conforms to VideoAnalysisInput schema
    test_data = [
        {
            "video_id": "vid-1",
            "title": "Test Video 1",
            "views": 100,
            "retention_avg_pct": 45.0,
            "type": "Shorts"
        },
        {
            "video_id": "vid-2",
            "title": "Test Video 2",
            "views": 200,
            "retention_avg_pct": 80.0,
            "type": "Long"
        }
    ]

    expected_df = pd.DataFrame(test_data)
    mock_inner_service.ingest_data.return_value = expected_df

    # 2. Setup repository and decorator
    repository = JsonlVideoRepository(temp_archive_file)
    archiving_service = ArchivingDataIngestionService(
        inner=mock_inner_service, repository=repository
    )

    # 3. Execute
    result_df = await archiving_service.ingest_data()

    # 4. Verify behavior
    # It should return the exact same dataframe
    pd.testing.assert_frame_equal(result_df, expected_df)

    # It should have written the file
    assert os.path.exists(temp_archive_file)

    # The file should contain 2 lines of JSON
    with open(temp_archive_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 2
    assert "vid-1" in lines[0]
    assert "Test Video 1" in lines[0]
    assert "vid-2" in lines[1]
    assert "Test Video 2" in lines[1]


def test_jsonl_repository_save_error(temp_archive_file: str) -> None:
    """
    Tests that JsonlVideoRepository raises an ArchivingError when saving fails.
    """
    # Force a permission error by creating a directory with the same name
    os.makedirs(temp_archive_file)

    repo = JsonlVideoRepository(temp_archive_file)

    item = VideoAnalysisInput(
        video_id="vid-error",
        title="Error Video",
        views=10,
        retention_avg_pct=10.0,
        type="Long"
    )

    with pytest.raises(ArchivingError, match="Persistence error"):
        repo.save(item)
