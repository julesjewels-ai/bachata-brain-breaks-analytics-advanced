"""
Tests for archival data ingestion service.
"""
import os
import json
import pytest
import pandas as pd
from unittest.mock import Mock, AsyncMock

from src.core.archival import (
    JsonFileRepository, ArchivingDataIngestionService
)
from src.core.interfaces import DataIngestionService

@pytest.fixture
def mock_inner_service() -> DataIngestionService:
    service = Mock(spec=DataIngestionService)

    # Mock data to return
    data = pd.DataFrame([
        {'video_id': 'vid_1', 'title': 'Test Video', 'views': 100, 'retention_avg_pct': 50.0, 'type': 'Long'}
    ])

    service.ingest_data = AsyncMock(return_value=data)
    return service

@pytest.fixture
def temp_filepath(tmp_path) -> str:
    return str(tmp_path / "test_archive.json")

@pytest.mark.asyncio
async def test_archiving_data_ingestion_service(
    mock_inner_service: DataIngestionService, temp_filepath: str
) -> None:
    """
    Test that ArchivingDataIngestionService correctly wraps inner service
    and archives the resulting DataFrame.
    """
    # Setup
    repository = JsonFileRepository(temp_filepath)
    archiving_service = ArchivingDataIngestionService(
        inner=mock_inner_service, repository=repository
    )

    # Execute
    result_df = await archiving_service.ingest_data()

    # Verify inner service was called
    assert isinstance(mock_inner_service.ingest_data, AsyncMock)
    mock_inner_service.ingest_data.assert_awaited_once()

    # Verify return value is the DataFrame
    assert isinstance(result_df, pd.DataFrame)
    assert len(result_df) == 1
    assert result_df.iloc[0]['video_id'] == 'vid_1'

    # Verify file was created and contains correct data
    assert os.path.exists(temp_filepath)

    with open(temp_filepath, 'r') as f:
        archived_data = json.load(f)

    assert isinstance(archived_data, list)
    assert len(archived_data) == 1
    assert archived_data[0]['video_id'] == 'vid_1'
    assert archived_data[0]['title'] == 'Test Video'
    assert archived_data[0]['views'] == 100
    assert archived_data[0]['retention_avg_pct'] == 50.0
    assert archived_data[0]['type'] == 'Long'
