import json
from unittest.mock import Mock, mock_open, patch

import pandas as pd
import pytest

from src.core.interfaces import DataIngestionService, ReportGenerator
from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsError,
    MetricsReportGenerator,
    record_telemetry,
)
from src.core.models import MetricEvent


@pytest.fixture
def mock_metric_event() -> MetricEvent:
    return MetricEvent(
        metric_name="test_metric",
        value=1.0,
        unit="count",
        tags={"status": "success"}
    )


def test_file_metrics_repository_record_success(
    mock_metric_event: MetricEvent
) -> None:
    repo = FileMetricsRepository("dummy.jsonl")

    with patch("builtins.open", mock_open()) as mocked_file:
        repo.record(mock_metric_event)

        mocked_file.assert_called_once_with("dummy.jsonl", "a")

        # Verify write was called with json string ending in newline
        handle = mocked_file()
        handle.write.assert_called_once()
        written_str = handle.write.call_args[0][0]

        assert written_str.endswith("\n")
        written_json = json.loads(written_str)
        assert written_json["metric_name"] == "test_metric"
        assert written_json["value"] == 1.0
        assert written_json["unit"] == "count"
        assert written_json["tags"] == {"status": "success"}
        assert "timestamp" in written_json


def test_file_metrics_repository_record_failure(
    mock_metric_event: MetricEvent
) -> None:
    repo = FileMetricsRepository("dummy.jsonl")

    with patch("builtins.open", side_effect=OSError("Disk full")):
        with pytest.raises(MetricsError) as exc_info:
            repo.record(mock_metric_event)

        assert "Persistence error:" in str(exc_info.value)


def test_record_telemetry_success() -> None:
    mock_repo = Mock(spec=FileMetricsRepository)

    with record_telemetry(mock_repo, "test_execution"):
        # block executes successfully
        pass

    mock_repo.record.assert_called_once()
    recorded_event = mock_repo.record.call_args[0][0]

    assert isinstance(recorded_event, MetricEvent)
    assert recorded_event.metric_name == "test_execution"
    assert recorded_event.tags.get("status") == "success"


def test_record_telemetry_failure() -> None:
    mock_repo = Mock(spec=FileMetricsRepository)

    class CustomTestException(Exception):
        pass

    with pytest.raises(CustomTestException):
        with record_telemetry(mock_repo, "test_execution"):
            raise CustomTestException("Test error")

    mock_repo.record.assert_called_once()
    recorded_event = mock_repo.record.call_args[0][0]

    assert isinstance(recorded_event, MetricEvent)
    assert recorded_event.metric_name == "test_execution"
    assert recorded_event.tags.get("status") == "failure"
    assert recorded_event.tags.get("base_error") == "CustomTestException"


@pytest.mark.asyncio
async def test_metrics_data_ingestion_service_success() -> None:
    mock_inner = Mock(spec=DataIngestionService)
    expected_df = pd.DataFrame({"A": [1, 2]})

    # Mocking async method
    async def mock_ingest_data() -> pd.DataFrame:
        return expected_df

    mock_inner.ingest_data = mock_ingest_data
    mock_repo = Mock(spec=FileMetricsRepository)

    service = MetricsDataIngestionService(mock_inner, mock_repo)
    result = await service.ingest_data()

    pd.testing.assert_frame_equal(result, expected_df)

    mock_repo.record.assert_called_once()
    recorded_event = mock_repo.record.call_args[0][0]
    assert recorded_event.metric_name == "ingestion_execution"
    assert recorded_event.tags.get("status") == "success"


def test_metrics_report_generator_success() -> None:
    mock_inner = Mock(spec=ReportGenerator)
    mock_repo = Mock(spec=FileMetricsRepository)

    service = MetricsReportGenerator(mock_inner, mock_repo)
    anomalies = {"test": pd.DataFrame()}
    strategy = "test_strategy"
    filepath = "report.xlsx"

    service.generate_report(anomalies, strategy, filepath)

    mock_inner.generate_report.assert_called_once_with(
        anomalies, strategy, filepath
    )

    mock_repo.record.assert_called_once()
    recorded_event = mock_repo.record.call_args[0][0]
    assert recorded_event.metric_name == "report_generation_execution"
    assert recorded_event.tags.get("status") == "success"
