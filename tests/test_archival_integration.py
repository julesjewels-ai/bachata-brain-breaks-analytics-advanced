"""
Integration tests for the Anomaly Archival feature.
Proves the feature works from Interface to Implementation.
"""
import json
import os
from unittest.mock import Mock

import pandas as pd
import pytest

from src.core.archival import ArchivalReportGenerator, FileAnomalyRepository
from src.core.interfaces import ReportGenerator


@pytest.fixture
def temp_archival_file(tmp_path):
    """Provides a temporary file path for anomaly persistence."""
    filepath = tmp_path / "test_anomalies.jsonl"
    yield str(filepath)
    if filepath.exists():
        os.remove(filepath)

def test_archival_report_generator_integration(temp_archival_file):
    """
    Tests that ArchivalReportGenerator correctly archives anomalies
    to a file and then delegates to the inner ReportGenerator.
    """
    # 1. Setup mock inner report generator
    mock_inner_generator = Mock(spec=ReportGenerator)

    # 2. Setup the real repository and the decorator
    repository = FileAnomalyRepository(filepath=temp_archival_file)
    archival_generator = ArchivalReportGenerator(
        inner=mock_inner_generator, repository=repository
    )

    # 3. Create dummy anomaly data
    df_shorts = pd.DataFrame([
        {
            'video_id': 'short_1',
            'title': 'Viral Short Dance',
            'views': 1000000,
            'retention_avg_pct': 95.5,
            'type': 'Shorts'
        }
    ])
    df_long = pd.DataFrame([
        {
            'video_id': 'long_1',
            'title': 'Deep Dive Tutorial',
            'views': 50000,
            'retention_avg_pct': 60.0,
            'type': 'Long'
        }
    ])

    anomalies = {
        'Shorts': df_shorts,
        'Long': df_long
    }

    strategy = "Test Strategy"
    report_filepath = "test_report.xlsx"

    # 4. Execute the decorator
    archival_generator.generate_report(anomalies, strategy, report_filepath)

    # 5. Verify the inner generator was called correctly
    mock_inner_generator.generate_report.assert_called_once_with(
        anomalies, strategy, report_filepath
    )

    # 6. Verify the file was written and contains the expected data
    assert os.path.exists(temp_archival_file)

    with open(temp_archival_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 2

    # Parse the JSON lines back to dicts
    record1 = json.loads(lines[0])
    record2 = json.loads(lines[1])

    # Sort by video_id for predictable assertion, just in case dict iteration order varies
    records = sorted([record1, record2], key=lambda x: x['video_id'])

    assert records[0]['video_id'] == 'long_1'
    assert records[0]['video_type'] == 'Long'
    assert records[0]['views'] == 50000

    assert records[1]['video_id'] == 'short_1'
    assert records[1]['video_type'] == 'Shorts'
    assert records[1]['views'] == 1000000

    # Ensure timestamp was generated correctly (not checking exact time, just existence)
    assert 'timestamp' in records[0]
    assert 'timestamp' in records[1]
