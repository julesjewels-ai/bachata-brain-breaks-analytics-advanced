import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, AsyncMock
import pandas as pd

from src.core.metrics import (
    FileMetricsRepository,
    MetricsError,
    record_telemetry,
    MetricsDataIngestionService,
    MetricsReportGenerator
)
from src.core.models import MetricEvent

def test_file_metrics_repository_record_success(tmp_path):
    filepath = tmp_path / "metrics.jsonl"
    repo = FileMetricsRepository(str(filepath))
    event = MetricEvent(
        metric_name="test_metric",
        value=42.0,
        unit="ms",
        tags={"source": "test"},
        timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    repo.record(event)

    assert filepath.exists()
    with open(filepath, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["metric_name"] == "test_metric"
        assert data["value"] == 42.0
        assert data["unit"] == "ms"
        assert data["tags"] == {"source": "test"}
        assert data["timestamp"] in ("2024-01-01T00:00:00Z", "2024-01-01T00:00:00+00:00")

def test_file_metrics_repository_record_error(tmp_path):
    filepath = tmp_path / "metrics.jsonl"
    repo = FileMetricsRepository(str(filepath))
    event = MetricEvent(
        metric_name="test_metric",
        value=42.0,
        unit="ms"
    )

    with patch("builtins.open", side_effect=PermissionError("Denied")):
        with pytest.raises(MetricsError) as exc_info:
            repo.record(event)
        assert "Persistence error:" in str(exc_info.value)

def test_record_telemetry_success():
    repo_mock = Mock(spec=FileMetricsRepository)

    with record_telemetry(repo_mock, "test_execution"):
        pass

    repo_mock.record.assert_called_once()
    called_event = repo_mock.record.call_args[0][0]
    assert isinstance(called_event, MetricEvent)
    assert called_event.metric_name == "test_execution"
    assert called_event.value == 1.0
    assert called_event.unit == "count"
    assert called_event.tags == {"status": "success"}

def test_record_telemetry_error():
    repo_mock = Mock(spec=FileMetricsRepository)

    with pytest.raises(ValueError, match="Test error"):
        with record_telemetry(repo_mock, "test_execution"):
            raise ValueError("Test error")

    repo_mock.record.assert_called_once()
    called_event = repo_mock.record.call_args[0][0]
    assert isinstance(called_event, MetricEvent)
    assert called_event.metric_name == "test_execution"
    assert called_event.value == 1.0
    assert called_event.unit == "count"
    assert called_event.tags == {"status": "failure", "base_error": "ValueError"}

@pytest.mark.asyncio
async def test_metrics_data_ingestion_service():
    inner_mock = AsyncMock()
    df = pd.DataFrame({"test": [1]})
    inner_mock.ingest_data.return_value = df

    repo_mock = Mock(spec=FileMetricsRepository)
    service = MetricsDataIngestionService(inner_mock, repo_mock)

    result = await service.ingest_data()
    assert result.equals(df)

    inner_mock.ingest_data.assert_called_once()
    repo_mock.record.assert_called_once()
    called_event = repo_mock.record.call_args[0][0]
    assert called_event.metric_name == "ingestion_execution"
    assert called_event.tags == {"status": "success"}

def test_metrics_report_generator():
    inner_mock = Mock()
    repo_mock = Mock(spec=FileMetricsRepository)
    service = MetricsReportGenerator(inner_mock, repo_mock)

    anomalies = {"Shorts": pd.DataFrame({"test": [1]})}
    service.generate_report(anomalies, "Strategy", "report.xlsx")

    inner_mock.generate_report.assert_called_once_with(anomalies, "Strategy", "report.xlsx")
    repo_mock.record.assert_called_once()
    called_event = repo_mock.record.call_args[0][0]
    assert called_event.metric_name == "report_generation_execution"
    assert called_event.tags == {"status": "success"}
