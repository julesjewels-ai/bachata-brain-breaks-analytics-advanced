import json

import pandas as pd
import pytest

from src.core.archiving import (
    ArchiveError,
    ArchivingDataIngestionService,
    JsonLinesRepository,
)
from src.core.interfaces import DataIngestionService
from src.core.models import VideoAnalysisInput


class MockIngestionService(DataIngestionService):
    async def ingest_data(self) -> pd.DataFrame:
        return pd.DataFrame({
            "video_id": ["vid1", "vid2"],
            "title": ["Title 1", "Title 2"],
            "views": [100, 200],
            "retention_avg_pct": [50.0, 60.0],
            "type": ["Long", "Shorts"]
        })

@pytest.fixture
def temp_archive_file(tmp_path):
    filepath = tmp_path / "archive.jsonl"
    yield str(filepath)
    if filepath.exists():
        filepath.unlink()

def test_json_lines_repository_path_traversal():
    with pytest.raises(ArchiveError, match="Path traversal"):
        JsonLinesRepository("../data.jsonl")

def test_json_lines_repository_save(temp_archive_file):
    repo = JsonLinesRepository[VideoAnalysisInput](temp_archive_file)
    item = VideoAnalysisInput(
        video_id="vid1", title="Title 1", views=100, retention_avg_pct=50.0, type="Long"
    )
    repo.save(item)

    with open(temp_archive_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["video_id"] == "vid1"

@pytest.mark.asyncio
async def test_archiving_data_ingestion_service(temp_archive_file):
    repo = JsonLinesRepository[VideoAnalysisInput](temp_archive_file)
    mock_service = MockIngestionService()
    archiving_service = ArchivingDataIngestionService(inner=mock_service, repository=repo)

    df = await archiving_service.ingest_data()
    assert not df.empty

    with open(temp_archive_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 2
        data1 = json.loads(lines[0])
        assert data1["video_id"] == "vid1"
        data2 = json.loads(lines[1])
        assert data2["video_id"] == "vid2"
