import json
import pytest
import os
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsReportGenerator,
    record_telemetry,
    MetricsError
)
from src.core.models import MetricEvent
from src.core.interfaces import DataIngestionService, ReportGenerator


def test_file_metrics_repository_record(tmp_path):
    filepath = str(tmp_path / "metrics.jsonl")
    repo = FileMetricsRepository(filepath)

    event = MetricEvent(
        metric_name="test_metric",
        value=1.0,
        unit="count",
        tags={"status": "success"},
        timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    )

    repo.record(event)

    assert os.path.exists(filepath)
    with open(filepath, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["metric_name"] == "test_metric"
        assert data["value"] == 1.0
        assert data["unit"] == "count"
        assert data["tags"] == {"status": "success"}
        assert "timestamp" in data

def test_file_metrics_repository_record_error(tmp_path):
    # Pass a directory path to trigger a file opening error
    repo = FileMetricsRepository(str(tmp_path))

    event = MetricEvent(
        metric_name="test_metric",
        value=1.0,
        unit="count"
    )

    with pytest.raises(MetricsError, match="Persistence error:"):
        repo.record(event)

def test_record_telemetry_success():
    mock_repo = MagicMock(spec=FileMetricsRepository)

    with record_telemetry(mock_repo, "test_execution"):
        pass

    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "test_execution"
    assert event.tags["status"] == "success"

def test_record_telemetry_failure():
    mock_repo = MagicMock(spec=FileMetricsRepository)

    with pytest.raises(ValueError):
        with record_telemetry(mock_repo, "test_execution"):
            raise ValueError("Test error")

    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "test_execution"
    assert event.tags["status"] == "failure"
    assert event.tags["base_error"] == "ValueError"

@pytest.mark.asyncio
async def test_metrics_data_ingestion_service():
    mock_inner = MagicMock(spec=DataIngestionService)
    mock_inner.ingest_data = AsyncMock(return_value=pd.DataFrame())
    mock_repo = MagicMock(spec=FileMetricsRepository)

    service = MetricsDataIngestionService(inner=mock_inner, repository=mock_repo)
    result = await service.ingest_data()

    assert isinstance(result, pd.DataFrame)
    mock_inner.ingest_data.assert_awaited_once()

    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "ingestion_execution"
    assert event.tags["status"] == "success"

def test_metrics_report_generator():
    mock_inner = MagicMock(spec=ReportGenerator)
    mock_repo = MagicMock(spec=FileMetricsRepository)

    generator = MetricsReportGenerator(inner=mock_inner, repository=mock_repo)

    generator.generate_report({"test": pd.DataFrame()}, "test strategy", "test.xlsx")

    mock_inner.generate_report.assert_called_once()

    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "report_generation_execution"
    assert event.tags["status"] == "success"
