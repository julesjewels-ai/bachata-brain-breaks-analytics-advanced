"""
Tests for data archiving mechanisms.
"""
import json
import os

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from src.core.archiving import (
    ArchiveRepository,
    ArchivingDataIngestionService,
    ArchivingError,
    JSONLArchiveRepository,
)
from src.core.interfaces import DataIngestionService


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Provides a sample DataFrame for testing."""
    return pd.DataFrame([
        {'video_id': '1', 'title': 'Test 1', 'views': 100},
        {'video_id': '2', 'title': 'Test 2', 'views': 200},
    ])


def test_jsonl_archive_repository_save(
    tmp_path: pytest.TempPathFactory, sample_df: pd.DataFrame
) -> None:
    """Test that JSONLArchiveRepository saves data properly."""
    filepath = os.path.join(str(tmp_path), "test_archive.jsonl")
    repo = JSONLArchiveRepository(filepath)

    repo.save(sample_df)

    assert os.path.exists(filepath)

    # Verify contents
    with open(filepath, 'r') as f:
        lines = [line for line in f if line.strip()]

    assert len(lines) == 2

    # Parse back the json
    record1 = json.loads(lines[0])
    record2 = json.loads(lines[1])

    assert record1['video_id'] == '1'
    assert record1['title'] == 'Test 1'
    assert 'archived_at' in record1

    assert record2['video_id'] == '2'
    assert record2['views'] == 200


def test_jsonl_archive_repository_save_error(tmp_path: pytest.TempPathFactory, sample_df: pd.DataFrame) -> None:
    """Test that ArchivingError is raised when saving fails."""
    # Create a directory with the same name as the target file to force an OSError
    filepath = os.path.join(str(tmp_path), "test_archive_error.jsonl")
    os.mkdir(filepath)

    repo = JSONLArchiveRepository(filepath)

    with pytest.raises(ArchivingError, match="Archiving persistence error"):
        repo.save(sample_df)


@pytest.mark.asyncio
async def test_archiving_data_ingestion_service(
    mocker: MockerFixture, sample_df: pd.DataFrame
) -> None:
    """Test that ArchivingDataIngestionService correctly delegates and saves."""
    # Mock the inner ingestion service
    mock_inner = mocker.Mock(spec=DataIngestionService)
    mock_inner.ingest_data = mocker.AsyncMock(return_value=sample_df)

    # Mock the repository
    mock_repo = mocker.Mock(spec=ArchiveRepository)
    mock_repo.save = mocker.Mock()

    service = ArchivingDataIngestionService(inner=mock_inner, repository=mock_repo)

    result_df = await service.ingest_data()

    # Verify inner service was called
    mock_inner.ingest_data.assert_called_once()

    # Verify repository save was called with the dataframe
    mock_repo.save.assert_called_once_with(sample_df)

    # Verify the original dataframe is returned
    pd.testing.assert_frame_equal(result_df, sample_df)


@pytest.mark.asyncio
async def test_archiving_data_ingestion_service_error_handling(
    mocker: MockerFixture, sample_df: pd.DataFrame
) -> None:
    """Test that ArchivingDataIngestionService swallows ArchivingError."""
    # Mock the inner ingestion service
    mock_inner = mocker.Mock(spec=DataIngestionService)
    mock_inner.ingest_data = mocker.AsyncMock(return_value=sample_df)

    # Mock the repository to raise an error
    mock_repo = mocker.Mock(spec=ArchiveRepository)
    mock_repo.save.side_effect = ArchivingError("Mock archiving error")

    service = ArchivingDataIngestionService(inner=mock_inner, repository=mock_repo)

    # The error should be caught, and the dataframe should still be returned
    result_df = await service.ingest_data()

    mock_repo.save.assert_called_once_with(sample_df)
    pd.testing.assert_frame_equal(result_df, sample_df)
