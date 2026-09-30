import json
import pytest
import pandas as pd
from pathlib import Path

from src.core.models import AnomalyRecord
from src.core.archiving import JSONLRepository, ArchivingReportGenerator, ArchivalError
from src.core.interfaces import ReportGenerator


class MockReportGenerator(ReportGenerator):
    def __init__(self):
        self.called = False
        self.anomalies = None
        self.strategy = None
        self.filepath = None

    def generate_report(self, anomalies, strategy, filepath):
        self.called = True
        self.anomalies = anomalies
        self.strategy = strategy
        self.filepath = filepath


class MockFailingRepository(JSONLRepository[AnomalyRecord]):
    def __init__(self, filepath: str) -> None:
        super().__init__(filepath)

    def save(self, item: AnomalyRecord) -> None:
        raise ArchivalError("Mock failure")


@pytest.fixture
def mock_anomalies_data():
    return {
        "Shorts": pd.DataFrame([
            {
                "video_id": "vid1",
                "title": "Short 1",
                "views": 1000,
                "retention_avg_pct": 80.5,
                "type": "Shorts"
            }
        ]),
        "Long": pd.DataFrame([
            {
                "video_id": "vid2",
                "title": "Long 1",
                "views": 500,
                "retention_avg_pct": 45.0,
                "type": "Long"
            }
        ])
    }


def test_archiving_report_generator_success(tmp_path: Path, mock_anomalies_data):
    """
    Tests that the ArchivingReportGenerator successfully persists records and calls
    the inner generator.
    """
    archive_file = tmp_path / "test_archive.jsonl"
    repository = JSONLRepository[AnomalyRecord](str(archive_file))
    inner_generator = MockReportGenerator()

    archiving_generator = ArchivingReportGenerator(inner=inner_generator, repository=repository)

    archiving_generator.generate_report(
        anomalies=mock_anomalies_data,
        strategy="Test Strategy",
        filepath="test_report.xlsx"
    )

    assert inner_generator.called is True
    assert inner_generator.filepath == "test_report.xlsx"

    # Verify file contents
    assert archive_file.exists()
    records = []
    with open(archive_file, 'r') as f:
        for line in f:
            records.append(json.loads(line))

    assert len(records) == 2
    assert records[0]["video_id"] == "vid1"
    assert records[1]["video_id"] == "vid2"


def test_archiving_report_generator_handles_archival_error(tmp_path: Path, mock_anomalies_data):
    """
    Tests that the ArchivingReportGenerator handles ArchivalError gracefully and
    still calls the inner generator.
    """
    archive_file = tmp_path / "test_archive.jsonl"
    repository = MockFailingRepository(str(archive_file))
    inner_generator = MockReportGenerator()

    archiving_generator = ArchivingReportGenerator(inner=inner_generator, repository=repository)

    archiving_generator.generate_report(
        anomalies=mock_anomalies_data,
        strategy="Test Strategy",
        filepath="test_report.xlsx"
    )

    # Inner generator should still be called
    assert inner_generator.called is True
    assert inner_generator.filepath == "test_report.xlsx"

    # File should not be created by the failing repo
    assert not archive_file.exists()
