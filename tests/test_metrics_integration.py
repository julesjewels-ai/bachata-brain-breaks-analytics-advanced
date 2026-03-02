"""
Integration tests for Metrics tracking module.
Verifies the full 'Interface to Implementation' flow using the Decorator pattern.
"""
import os
import json
import pytest
import pandas as pd
from typing import Dict, Any, Type
from unittest.mock import Mock

from src.core.models import MetricEvent
from src.core.metrics import (
    FileMetricsRepository,
    MetricsDataIngestionService,
    MetricsReportGenerator,
    MetricsError
)
from src.core.interfaces import DataIngestionService, ReportGenerator


class MockDataIngestionService(DataIngestionService):
    def __init__(self, should_fail: bool = False, records: int = 5):
        self.should_fail = should_fail
        self.records = records

    def ingest_data(self) -> pd.DataFrame:
        if self.should_fail:
            raise ValueError("Simulated ingestion failure")
        return pd.DataFrame([{"id": i} for i in range(self.records)])


class MockReportGenerator(ReportGenerator):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        if self.should_fail:
            raise RuntimeError("Simulated reporting failure")
        pass


@pytest.fixture
def metrics_file(tmp_path: Any) -> str:
    """Fixture providing a temporary file path for metrics storage."""
    file_path = tmp_path / "test_metrics.jsonl"
    return str(file_path)


@pytest.fixture
def repo(metrics_file: str) -> FileMetricsRepository:
    """Fixture providing a FileMetricsRepository instance."""
    return FileMetricsRepository(filepath=metrics_file)


def test_metrics_data_ingestion_success(
    repo: FileMetricsRepository, metrics_file: str
) -> None:
    """Test successful data ingestion metrics tracking."""
    base_service = MockDataIngestionService(should_fail=False, records=10)
    decorated_service = MetricsDataIngestionService(
        base_service=base_service, repository=repo
    )

    result = decorated_service.ingest_data()
    assert len(result) == 10

    assert os.path.exists(metrics_file)
    with open(metrics_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        event_dict = json.loads(lines[0])

        assert event_dict["metric_name"] == "ingestion_duration"
        assert event_dict["unit"] == "seconds"
        assert event_dict["tags"]["status"] == "success"
        assert event_dict["tags"]["records"] == "10"
        assert "base_error" not in event_dict["tags"]
        assert event_dict["value"] >= 0


def test_metrics_data_ingestion_error(
    repo: FileMetricsRepository, metrics_file: str
) -> None:
    """Test data ingestion metrics tracking when an error occurs."""
    base_service = MockDataIngestionService(should_fail=True)
    decorated_service = MetricsDataIngestionService(
        base_service=base_service, repository=repo
    )

    with pytest.raises(ValueError, match="Simulated ingestion failure"):
        decorated_service.ingest_data()

    assert os.path.exists(metrics_file)
    with open(metrics_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        event_dict = json.loads(lines[0])

        assert event_dict["metric_name"] == "ingestion_duration"
        assert event_dict["tags"]["status"] == "error"
        assert event_dict["tags"]["base_error"] == "ValueError"
        assert "records" not in event_dict["tags"]
        assert event_dict["value"] >= 0


def test_metrics_report_generator_success(
    repo: FileMetricsRepository, metrics_file: str
) -> None:
    """Test successful report generation metrics tracking."""
    base_service = MockReportGenerator(should_fail=False)
    decorated_service = MetricsReportGenerator(
        base_service=base_service, repository=repo
    )

    filepath = "test_output.xlsx"
    decorated_service.generate_report({}, "strategy", filepath)

    assert os.path.exists(metrics_file)
    with open(metrics_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        event_dict = json.loads(lines[0])

        assert event_dict["metric_name"] == "report_generation_duration"
        assert event_dict["unit"] == "seconds"
        assert event_dict["tags"]["status"] == "success"
        assert event_dict["tags"]["filepath"] == filepath
        assert "base_error" not in event_dict["tags"]
        assert event_dict["value"] >= 0


def test_metrics_report_generator_error(
    repo: FileMetricsRepository, metrics_file: str
) -> None:
    """Test report generation metrics tracking when an error occurs."""
    base_service = MockReportGenerator(should_fail=True)
    decorated_service = MetricsReportGenerator(
        base_service=base_service, repository=repo
    )

    filepath = "test_error_output.xlsx"
    with pytest.raises(RuntimeError, match="Simulated reporting failure"):
        decorated_service.generate_report({}, "strategy", filepath)

    assert os.path.exists(metrics_file)
    with open(metrics_file, "r") as f:
        lines = f.readlines()
        assert len(lines) == 1
        event_dict = json.loads(lines[0])

        assert event_dict["metric_name"] == "report_generation_duration"
        assert event_dict["tags"]["status"] == "error"
        assert event_dict["tags"]["base_error"] == "RuntimeError"
        assert event_dict["tags"]["filepath"] == filepath
        assert event_dict["value"] >= 0


def test_repository_save_error(tmp_path: Any) -> None:
    """Test error handling in FileMetricsRepository when save fails."""
    # Create a directory path to intentionally fail file open
    dir_path = str(tmp_path / "invalid_file.jsonl")
    os.mkdir(dir_path)

    repo = FileMetricsRepository(filepath=dir_path)
    event = MetricEvent(
        metric_name="test",
        value=1.0,
        unit="test_unit",
        tags={"test": "tag"}
    )

    with pytest.raises(MetricsError, match="Failed to write metric"):
        repo.save(event)
