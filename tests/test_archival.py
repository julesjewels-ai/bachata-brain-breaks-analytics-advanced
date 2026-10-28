import json
from pathlib import Path

import pandas as pd
import pytest

from src.core.archival import ArchivalDataIngestionService, FileArchivalRepository
from src.core.interfaces import DataIngestionService


class MockDataIngestionService(DataIngestionService):
    async def ingest_data(self) -> pd.DataFrame:
        data = {
            "video_id": ["v1", "v2"],
            "title": ["Test 1", "Test 2"],
            "views": [100, 200]
        }
        return pd.DataFrame(data)


@pytest.mark.asyncio
async def test_archival_integration(tmp_path: Path) -> None:
    # Arrange
    archive_dir = str(tmp_path / ".archive")
    repository = FileArchivalRepository(archive_dir)
    mock_ingestion = MockDataIngestionService()

    archival_service = ArchivalDataIngestionService(
        inner=mock_ingestion,
        repository=repository,
        source_name="test_source"
    )

    # Act
    df = await archival_service.ingest_data()

    # Assert - ensure returned data is unchanged
    assert len(df) == 2
    assert "video_id" in df.columns

    # Assert - ensure files were created
    files = list(Path(archive_dir).glob("*"))
    assert len(files) == 2 # 1 csv, 1 json

    csv_file = next(f for f in files if f.suffix == ".csv")
    json_file = next(f for f in files if f.suffix == ".json")

    # Verify CSV content
    archived_df = pd.read_csv(csv_file)
    assert len(archived_df) == 2
    assert archived_df.iloc[0]["video_id"] == "v1"

    # Verify JSON content
    with open(json_file, "r") as f:  # noqa: ASYNC230
        metadata = json.load(f)

    assert metadata["source"] == "test_source"
    assert metadata["record_count"] == 2
    assert "timestamp" in metadata
