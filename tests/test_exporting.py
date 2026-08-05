import json
import pytest
from unittest.mock import AsyncMock, Mock
import pandas as pd
from typing import Any
from src.core.models import VideoAnalysisInput
from src.core.exporting import (
    JsonLinesExporter,
    ExportError,
    ExportingDataIngestionService,
)


def test_json_lines_exporter_exports_data(tmp_path: Any) -> None:
    """Verifies that JsonLinesExporter correctly saves valid domain models to JSONL."""
    filepath = tmp_path / "test_export.jsonl"
    exporter = JsonLinesExporter[VideoAnalysisInput]()

    items = [
        VideoAnalysisInput(
            video_id="test1",
            title="Video 1",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        ),
        VideoAnalysisInput(
            video_id="test2",
            title="Video 2",
            views=200,
            retention_avg_pct=60.0,
            type="Shorts"
        ),
    ]

    exporter.export_batch(items, str(filepath))

    # Verify file contents
    assert filepath.exists()
    lines = filepath.read_text().strip().split('\n')
    assert len(lines) == 2

    data1 = json.loads(lines[0])
    assert data1["video_id"] == "test1"
    assert data1["title"] == "Video 1"

    data2 = json.loads(lines[1])
    assert data2["video_id"] == "test2"
    assert data2["title"] == "Video 2"


@pytest.mark.parametrize("invalid_path", [
    "../config/secrets.jsonl",
    "/etc/passwd",
    "test_export.csv",  # Not .jsonl
])
def test_json_lines_exporter_path_traversal(invalid_path: str) -> None:
    """Verifies that JsonLinesExporter raises ExportError on unsafe paths."""
    exporter = JsonLinesExporter[VideoAnalysisInput]()
    items = [
        VideoAnalysisInput(
            video_id="test1",
            title="Video 1",
            views=100,
            retention_avg_pct=50.0,
            type="Long"
        )
    ]

    with pytest.raises(ExportError, match="Invalid or unsafe export path"):
        exporter.export_batch(items, invalid_path)


@pytest.mark.asyncio
async def test_exporting_data_ingestion_service_delegates() -> None:
    """Verifies the decorator delegates to the inner service and calls the exporter."""
    # Mock the inner ingestion service
    mock_inner = AsyncMock()
    mock_inner.ingest_data.return_value = pd.DataFrame([
        {
            "video_id": "test1",
            "title": "Decorated Video 1",
            "views": 300,
            "retention_avg_pct": 70.0,
            "type": "Shorts"
        }
    ])

    # Mock the exporter
    mock_exporter = Mock()

    # Setup decorator
    service = ExportingDataIngestionService(
        inner=mock_inner,
        exporter=mock_exporter,
        model_class=VideoAnalysisInput,
        export_filepath="dummy_path.jsonl"
    )

    # Execute
    df = await service.ingest_data()

    # Assert inner was called
    mock_inner.ingest_data.assert_awaited_once()

    # Assert DataFrame returned correctly
    assert len(df) == 1
    assert df.iloc[0]["video_id"] == "test1"

    # Assert exporter was called with mapped domain models
    mock_exporter.export_batch.assert_called_once()
    call_args = mock_exporter.export_batch.call_args[0]

    items = call_args[0]
    filepath = call_args[1]

    assert filepath == "dummy_path.jsonl"
    assert len(items) == 1
    assert isinstance(items[0], VideoAnalysisInput)
    assert items[0].video_id == "test1"
    assert items[0].title == "Decorated Video 1"
