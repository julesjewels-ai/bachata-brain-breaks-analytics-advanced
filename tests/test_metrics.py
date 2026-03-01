"""
Unit and integration tests for metrics reporting utility feature.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch
import pandas as pd

from src.core.models import MetricEvent
from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsReportGenerator,
    MetricsError
)
from src.core.ingestion import SimulationDataIngestionService


@pytest.fixture
def temp_metrics_file(tmp_path: Path) -> Path:
    """Fixture for a temporary metrics JSONL file."""
    return tmp_path / "test_metrics.jsonl"


def test_file_repository_save(temp_metrics_file: Path) -> None:
    """
    Test that FileMetricsRepository correctly appends JSONL lines.
    """
    repo = FileMetricsRepository(str(temp_metrics_file))
    event = MetricEvent(
        metric_name="test_metric",
        value=42.0,
        unit="ms",
        tags={"env": "test"}
    )
    repo.save(event)

    assert temp_metrics_file.exists()
    content = temp_metrics_file.read_text(encoding="utf-8").strip()
    data = json.loads(content)

    assert data["metric_name"] == "test_metric"
    assert data["value"] == 42.0
    assert data["unit"] == "ms"
    assert data["tags"] == {"env": "test"}
    assert "timestamp" in data


def test_file_repository_save_error(temp_metrics_file: Path) -> None:
    """
    Test that FileMetricsRepository handles write errors.
    """
    repo = FileMetricsRepository(str(temp_metrics_file))
    event = MetricEvent(metric_name="test", value=1.0, unit="ms")

    # Mock open to raise IOError
    with patch("pathlib.Path.open", side_effect=IOError("Mock error")):
        with pytest.raises(
            MetricsError, match="Failed to write metric event: Mock error"
        ):
            repo.save(event)


def test_metrics_data_ingestion_decorator() -> None:
    """
    Test that MetricsDataIngestionService records telemetry and calls wrapped
    service.
    """
    mock_service = Mock()
    mock_df = pd.DataFrame({"id": [1, 2, 3]})
    mock_service.ingest_data.return_value = mock_df

    mock_repo = Mock()

    decorator = MetricsDataIngestionService(
        service=mock_service, repository=mock_repo
    )
    result_df = decorator.ingest_data()

    assert result_df.equals(mock_df)
    mock_service.ingest_data.assert_called_once()

    mock_repo.save.assert_called_once()
    event = mock_repo.save.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "data_ingestion"
    assert event.tags["status"] == "success"
    assert event.tags["row_count"] == "3"
    assert event.value >= 0  # Duration should be positive


def test_metrics_data_ingestion_decorator_error() -> None:
    """
    Test that MetricsDataIngestionService records telemetry even on error.
    """
    mock_service = Mock()
    mock_service.ingest_data.side_effect = ValueError("Test error")

    mock_repo = Mock()

    decorator = MetricsDataIngestionService(
        service=mock_service, repository=mock_repo
    )

    with pytest.raises(ValueError, match="Test error"):
        decorator.ingest_data()

    mock_repo.save.assert_called_once()
    event = mock_repo.save.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "data_ingestion"
    assert event.tags["status"] == "error: ValueError"
    assert event.tags["row_count"] == "0"
    assert event.value >= 0


def test_metrics_report_generator_decorator() -> None:
    """
    Test that MetricsReportGenerator records telemetry and calls wrapped
    service.
    """
    mock_generator = Mock()
    mock_repo = Mock()

    decorator = MetricsReportGenerator(
        generator=mock_generator, repository=mock_repo
    )

    anomalies = {"test": pd.DataFrame()}
    strategy = "test_strategy"
    filepath = "test.xlsx"

    decorator.generate_report(anomalies, strategy, filepath)

    mock_generator.generate_report.assert_called_once_with(
        anomalies, strategy, filepath
    )

    mock_repo.save.assert_called_once()
    event = mock_repo.save.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "report_generation"
    assert event.tags["status"] == "success"
    assert event.tags["strategy"] == "test_strategy"
    assert event.value >= 0


def test_metrics_report_generator_decorator_error() -> None:
    """
    Test that MetricsReportGenerator records telemetry even on error.
    """
    mock_generator = Mock()
    mock_generator.generate_report.side_effect = TypeError("Test err")
    mock_repo = Mock()

    decorator = MetricsReportGenerator(
        generator=mock_generator, repository=mock_repo)

    with pytest.raises(TypeError, match="Test err"):
        decorator.generate_report({"test": pd.DataFrame()}, "strategy", "path")

    mock_repo.save.assert_called_once()
    event = mock_repo.save.call_args[0][0]
    assert isinstance(event, MetricEvent)
    assert event.metric_name == "report_generation"
    assert event.tags["status"] == "error: TypeError"
    assert event.tags["strategy"] == "strategy"
    assert event.value >= 0


def test_metrics_e2e_integration(temp_metrics_file: Path) -> None:
    """
    End-to-end integration test for the metrics utility feature.
    Verifies that real implementations interact correctly and write telemetry.
    """
    # 1. Setup FileMetricsRepository
    repo = FileMetricsRepository(str(temp_metrics_file))

    # 2. Setup real DataIngestionService and wrap it
    base_service = SimulationDataIngestionService()
    decorated_service = MetricsDataIngestionService(
        service=base_service, repository=repo
    )

    # 3. Perform action
    df = decorated_service.ingest_data()

    # 4. Verify original behavior is intact
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert "video_id" in df.columns

    # 5. Verify telemetry side-effect
    assert temp_metrics_file.exists()
    content = temp_metrics_file.read_text(encoding="utf-8").strip()

    # Check that a valid JSON line was written
    events = [json.loads(line) for line in content.split("\n") if line]
    assert len(events) == 1

    event_data = events[0]
    assert event_data["metric_name"] == "data_ingestion"
    assert event_data["tags"]["status"] == "success"
    assert int(event_data["tags"]["row_count"]) == len(df)
    assert event_data["value"] > 0
    assert event_data["unit"] == "ms"
    assert "timestamp" in event_data
