"""
Tests for the archiving service layer.
"""
import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pandas as pd
import pytest

from src.core.archiving import (
    ArchiveError,
    AutomatedDataArchiver,
    DataArchivingIngestionService,
    JsonlRepository,
)
from src.core.models import MetricEvent


@pytest.fixture
def mock_df() -> pd.DataFrame:
    data = [
        {"video_id": "v1", "title": "Test 1", "views": 100},
        {"video_id": "v2", "title": "Test 2", "views": 200},
    ]
    return pd.DataFrame(data)


@pytest.mark.asyncio
async def test_archiving_ingestion_service_integration(mock_df: pd.DataFrame, tmp_path: Any) -> None:
    """Test that data is successfully archived after ingestion."""
    archive_path = tmp_path / "test_archive.jsonl"
    mock_inner = AsyncMock()
    mock_inner.ingest_data.return_value = mock_df

    archiver = AutomatedDataArchiver(str(archive_path))
    service = DataArchivingIngestionService(inner=mock_inner, archiver=archiver)

    result_df = await service.ingest_data()

    # The original dataframe should be returned
    pd.testing.assert_frame_equal(result_df, mock_df)
    mock_inner.ingest_data.assert_awaited_once()

    # The file should exist and have 2 records
    assert archive_path.exists()
    records = []
    with open(archive_path, 'r') as f:  # noqa: ASYNC230
        for line in f:
            records.append(json.loads(line))

    assert len(records) == 2
    assert records[0]["video_id"] == "v1"
    assert records[1]["title"] == "Test 2"


@pytest.mark.asyncio
async def test_archiving_ingestion_service_failure(mock_df: pd.DataFrame) -> None:
    """Test that if archiving fails, the exception is swallowed and original DF returned."""
    mock_inner = AsyncMock()
    mock_inner.ingest_data.return_value = mock_df

    mock_archiver = Mock()
    mock_archiver.archive.side_effect = ArchiveError("Simulated archive failure")

    service = DataArchivingIngestionService(inner=mock_inner, archiver=mock_archiver)

    result_df = await service.ingest_data()

    # The error should be caught and not bubble up
    # The original dataframe should be returned
    pd.testing.assert_frame_equal(result_df, mock_df)
    mock_archiver.archive.assert_called_once_with(mock_df)


def test_jsonl_repository_save(tmp_path: Any) -> None:
    """Test generic model persistence via JsonlRepository."""
    repo_path = tmp_path / "test_repo.jsonl"
    repo: JsonlRepository[MetricEvent] = JsonlRepository(str(repo_path))

    event = MetricEvent(
        metric_name="test_metric",
        value=1.5,
        unit="test"
    )

    repo.save(event)

    assert repo_path.exists()
    with open(repo_path, 'r') as f:
        content = f.read()
        assert "test_metric" in content
        assert "1.5" in content

def test_automated_data_archiver_failure(tmp_path: Any) -> None:
    """Test AutomatedDataArchiver raises ArchiveError on file error."""
    # Attempt to write to a directory path which should fail
    archiver = AutomatedDataArchiver(str(tmp_path))
    df = pd.DataFrame([{"a": 1}])
    with pytest.raises(ArchiveError, match="Archiving error"):
        archiver.archive(df)
