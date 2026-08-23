"""
Unit tests for the metrics tracking system.
"""
import json
from unittest.mock import AsyncMock, MagicMock

import pandas as pd
import pytest

from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsError,
    MetricsReportGenerator,
)
from src.core.models import MetricEvent


@pytest.fixture
def metric_event():
    return MetricEvent(
        metric_name="test_metric",
        value=1.0,
        unit="test_unit",
        tags={"tag1": "value1"}
    )


def test_file_metrics_repository_record(tmp_path, metric_event):
    """Test successful recording of a metric event."""
    filepath = tmp_path / "metrics.jsonl"
    repo = FileMetricsRepository(str(filepath))
    repo.record(metric_event)

    assert filepath.exists()

    with open(filepath, 'r') as f:
        lines = f.readlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["metric_name"] == "test_metric"
        assert data["value"] == 1.0
        assert data["unit"] == "test_unit"
        assert data["tags"] == {"tag1": "value1"}
        assert "timestamp" in data


def test_file_metrics_repository_record_error(tmp_path, metric_event, monkeypatch):
    """Test that MetricsError is raised when file writing fails."""
    # We simulate an error by making the path a directory instead of a file
    filepath = tmp_path / "invalid_metrics.jsonl"
    filepath.mkdir()

    repo = FileMetricsRepository(str(filepath))

    with pytest.raises(MetricsError) as exc_info:
        repo.record(metric_event)

    assert "Persistence error" in str(exc_info.value)


@pytest.mark.asyncio
async def test_metrics_data_ingestion_service_success():
    """Test that data ingestion service decorator records success telemetry."""
    mock_ingestion = MagicMock()
    mock_ingestion.ingest_data = AsyncMock(return_value=pd.DataFrame([{"data": 1}]))

    mock_repo = MagicMock(spec=FileMetricsRepository)

    service = MetricsDataIngestionService(inner=mock_ingestion, repository=mock_repo)
    result = await service.ingest_data()

    assert len(result) == 1
    mock_ingestion.ingest_data.assert_awaited_once()

    # Verify telemetry was recorded
    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "ingestion_execution"
    assert event.tags["status"] == "success"


@pytest.mark.asyncio
async def test_metrics_data_ingestion_service_failure():
    """Test that data ingestion service decorator records failure telemetry."""
    mock_ingestion = MagicMock()
    mock_ingestion.ingest_data = AsyncMock(side_effect=ValueError("Failed to ingest"))

    mock_repo = MagicMock(spec=FileMetricsRepository)

    service = MetricsDataIngestionService(inner=mock_ingestion, repository=mock_repo)

    with pytest.raises(ValueError):
        await service.ingest_data()

    mock_ingestion.ingest_data.assert_awaited_once()

    # Verify failure telemetry was recorded
    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "ingestion_execution"
    assert event.tags["status"] == "failure"
    assert event.tags["base_error"] == "ValueError"


def test_metrics_report_generator_success():
    """Test that report generator decorator records success telemetry."""
    mock_report = MagicMock()

    mock_repo = MagicMock(spec=FileMetricsRepository)

    service = MetricsReportGenerator(inner=mock_report, repository=mock_repo)

    anomalies = {"test": pd.DataFrame()}
    strategy = "test strategy"
    filepath = "report.xlsx"

    service.generate_report(anomalies, strategy, filepath)

    mock_report.generate_report.assert_called_once_with(anomalies, strategy, filepath)

    # Verify telemetry was recorded
    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "report_generation_execution"
    assert event.tags["status"] == "success"


def test_metrics_report_generator_failure():
    """Test that report generator decorator records failure telemetry."""
    mock_report = MagicMock()
    mock_report.generate_report.side_effect = RuntimeError("Generation failed")

    mock_repo = MagicMock(spec=FileMetricsRepository)

    service = MetricsReportGenerator(inner=mock_report, repository=mock_repo)

    anomalies = {"test": pd.DataFrame()}
    strategy = "test strategy"
    filepath = "report.xlsx"

    with pytest.raises(RuntimeError):
        service.generate_report(anomalies, strategy, filepath)

    mock_report.generate_report.assert_called_once_with(anomalies, strategy, filepath)

    # Verify failure telemetry was recorded
    mock_repo.record.assert_called_once()
    event = mock_repo.record.call_args[0][0]
    assert event.metric_name == "report_generation_execution"
    assert event.tags["status"] == "failure"
    assert event.tags["base_error"] == "RuntimeError"
