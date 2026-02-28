import json
import pytest
import pandas as pd
from unittest.mock import Mock
from src.core.models import MetricEvent
from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsReportGenerator
)


@pytest.fixture
def metrics_file(tmp_path):
    filepath = tmp_path / "test_metrics.jsonl"
    yield filepath
    if filepath.exists():
        filepath.unlink()


def test_file_metrics_repository_records_event(metrics_file):
    repo = FileMetricsRepository(filepath=str(metrics_file))
    event = MetricEvent(
        metric_name="test_metric",
        value=1.23,
        unit="seconds",
        tags={"status": "success"}
    )

    repo.record(event)

    assert metrics_file.exists()
    with open(metrics_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["metric_name"] == "test_metric"
        assert data["value"] == 1.23
        assert data["unit"] == "seconds"
        assert data["tags"] == {"status": "success"}
        assert "timestamp" in data


def test_metrics_data_ingestion_service_success():
    base_service = Mock()
    mock_df = pd.DataFrame({'id': [1, 2, 3]})
    base_service.ingest_data.return_value = mock_df

    metrics_repo = Mock()

    service = MetricsDataIngestionService(
        base_service=base_service,
        metrics_repo=metrics_repo
    )

    result = service.ingest_data()

    assert result.equals(mock_df)
    base_service.ingest_data.assert_called_once()

    metrics_repo.record.assert_called_once()
    event = metrics_repo.record.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "ingestion_duration"
    assert event.unit == "seconds"
    assert event.tags["status"] == "success"
    assert event.tags["row_count"] == 3
    assert event.value >= 0


def test_metrics_data_ingestion_service_failure():
    base_service = Mock()
    base_service.ingest_data.side_effect = ValueError("Ingestion failed")

    metrics_repo = Mock()

    service = MetricsDataIngestionService(
        base_service=base_service,
        metrics_repo=metrics_repo
    )

    with pytest.raises(ValueError):
        service.ingest_data()

    base_service.ingest_data.assert_called_once()

    metrics_repo.record.assert_called_once()
    event = metrics_repo.record.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "ingestion_duration"
    assert event.unit == "seconds"
    assert event.tags["status"] == "failure"
    assert event.tags["row_count"] == 0
    assert event.value >= 0


def test_metrics_report_generator_success():
    base_service = Mock()
    metrics_repo = Mock()

    service = MetricsReportGenerator(
        base_service=base_service,
        metrics_repo=metrics_repo
    )

    anomalies = {
        "shorts": pd.DataFrame({'id': [1, 2]}),
        "long": pd.DataFrame({'id': [3]})
    }

    service.generate_report(anomalies, "test_strategy", "output.xlsx")

    base_service.generate_report.assert_called_once_with(
        anomalies, "test_strategy", "output.xlsx"
    )

    metrics_repo.record.assert_called_once()
    event = metrics_repo.record.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "report_generation_duration"
    assert event.unit == "seconds"
    assert event.tags["status"] == "success"
    assert event.tags["anomaly_count"] == 3
    assert event.tags["filepath"] == "output.xlsx"
    assert event.value >= 0


def test_metrics_report_generator_failure():
    base_service = Mock()
    base_service.generate_report.side_effect = IOError("File error")
    metrics_repo = Mock()

    service = MetricsReportGenerator(
        base_service=base_service,
        metrics_repo=metrics_repo
    )

    anomalies = {"shorts": pd.DataFrame({'id': [1, 2]})}

    with pytest.raises(IOError):
        service.generate_report(anomalies, "test_strategy", "output.xlsx")

    base_service.generate_report.assert_called_once()

    metrics_repo.record.assert_called_once()
    event = metrics_repo.record.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "report_generation_duration"
    assert event.unit == "seconds"
    assert event.tags["status"] == "failure"
    assert event.tags["anomaly_count"] == 2
    assert event.value >= 0
