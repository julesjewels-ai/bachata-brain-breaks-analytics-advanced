import os
import json
import tempfile
import pandas as pd
import pytest

from src.core.models import AnomalyRecord
from src.core.archival import (
    FileRepository, DefaultAnomalyArchiver, ArchivalError
)


def test_archival_integration() -> None:
    """
    Tests full archival workflow from domain service to generic repository.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        filepath = os.path.join(tmpdir, "test_anomalies.jsonl")

        # Initialize repository and archiver
        repo = FileRepository[AnomalyRecord](filepath)
        archiver = DefaultAnomalyArchiver(repository=repo)

        # Create mock anomaly data
        mock_data_shorts = pd.DataFrame([
            {"video_id": "v1", "title": "Test Short 1",
                "views": 150000, "retention_avg_pct": 95.5},
            {"video_id": "v2", "title": "Test Short 2",
                "views": 200000, "retention_avg_pct": 98.0}
        ])

        mock_data_long = pd.DataFrame([
            {"video_id": "v3", "title": "Test Long 1",
                "views": 50000, "retention_avg_pct": 55.0}
        ])

        anomalies = {
            "Shorts": mock_data_shorts,
            "Long": mock_data_long,
            "Empty": pd.DataFrame()
        }

        # Perform archival
        archiver.archive(anomalies)

        # Verify file creation and contents
        assert os.path.exists(filepath), "Archive file was not created"

        records = []
        with open(filepath, 'r') as f:
            for line in f:
                records.append(json.loads(line))

        assert len(records) == 3, "Expected 3 records to be archived"

        # Verify Pydantic validation worked through the archiver
        v1_record = next(r for r in records if r["video_id"] == "v1")
        assert v1_record["type"] == "Shorts"
        assert v1_record["views"] == 150000
        assert "detected_at" in v1_record

        v3_record = next(r for r in records if r["video_id"] == "v3")
        assert v3_record["type"] == "Long"
        assert v3_record["retention_avg_pct"] == 55.0


def test_archival_error_handling(mocker) -> None:
    """
    Tests that repository errors are correctly wrapped in ArchivalError.
    """
    repo = FileRepository[AnomalyRecord](
        "/invalid/path/that/should/fail.jsonl")

    # Mock open to force an error just in case /invalid/path is somehow
    # writable or mock environment
    mocker.patch(
        "builtins.open",
        side_effect=PermissionError("Mocked permission denied"))

    archiver = DefaultAnomalyArchiver(repository=repo)

    mock_data = pd.DataFrame([
        {"video_id": "v1", "title": "Test", "views": 100,
         "retention_avg_pct": 50.0}
    ])
    anomalies = {"Shorts": mock_data}

    err_msg = "Failed to persist records: Mocked permission denied"
    with pytest.raises(ArchivalError, match=err_msg):
        archiver.archive(anomalies)
