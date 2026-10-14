"""
Integration tests for the archiving module.
Verifies that ArchivedReportGenerator correctly coordinates with the underlying
ReportGenerator and the JSONLReportMetadataRepository.
"""
import os
import json
import pytest
import pandas as pd
from typing import Dict

from src.core.interfaces import ReportGenerator
from src.core.archiving import (
    JSONLReportMetadataRepository,
    ArchivedReportGenerator
)

class MockReportGenerator(ReportGenerator):
    """A mock report generator that just tracks if it was called."""
    def __init__(self):
        self.called = False
        self.last_filepath = None

    def generate_report(
        self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str
    ) -> None:
        self.called = True
        self.last_filepath = filepath

@pytest.fixture
def temp_archive_file(tmp_path) -> str:
    """Provides a temporary file path for the archive."""
    return str(tmp_path / "test_archive.jsonl")

def test_archived_report_generator_integration(temp_archive_file: str) -> None:
    """
    Tests the full flow: decorator -> mock generator + real file repository.
    """
    # Setup
    mock_generator = MockReportGenerator()
    repo = JSONLReportMetadataRepository(temp_archive_file)
    archived_generator = ArchivedReportGenerator(
        inner=mock_generator, repository=repo
    )

    anomalies = {
        "Shorts": pd.DataFrame({"views": [1000, 2000]}),
        "Long": pd.DataFrame({"views": [500]})
    }
    strategy = "This is a test strategy. " * 10 # make it longer than 100 chars
    report_filepath = "test_report.xlsx"

    # Act
    archived_generator.generate_report(anomalies, strategy, report_filepath)

    # Assert generator was called
    assert mock_generator.called, "The inner report generator was not called"
    assert mock_generator.last_filepath == report_filepath

    # Assert file was written
    assert os.path.exists(temp_archive_file), "Archive file was not created"

    # Assert file contents are correct
    with open(temp_archive_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 1, "Expected exactly one line in the archive"

    record = json.loads(lines[0])
    assert record["filepath"] == report_filepath
    assert record["anomaly_count"] == 3 # 2 + 1
    assert record["strategy_preview"] == strategy[:100] + "..."
    assert "timestamp" in record
