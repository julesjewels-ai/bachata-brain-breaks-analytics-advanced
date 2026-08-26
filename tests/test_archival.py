import json
from unittest.mock import Mock

import pandas as pd
import pytest

from src.core.archival import (
    ArchivalError,
    ArchivalReportGeneratorDecorator,
    FileAnomalyRepository,
)
from src.core.models import AnomalyRecord


def test_archival_report_generator_decorator(tmp_path):
    repo_file = tmp_path / "anomalies_archive.jsonl"
    repo = FileAnomalyRepository(str(repo_file))
    inner_report_generator = Mock()

    decorator = ArchivalReportGeneratorDecorator(
        inner=inner_report_generator, repository=repo
    )

    df_shorts = pd.DataFrame([
        {
            'video_id': 'vid_short_1',
            'title': 'Viral Short',
            'views': 100000,
            'retention_avg_pct': 90.0,
        }
    ])

    df_long = pd.DataFrame([
        {
            'video_id': 'vid_long_1',
            'title': 'Viral Long',
            'views': 500000,
            'retention_avg_pct': 70.0,
        }
    ])

    anomalies = {
        'Shorts': df_shorts,
        'Long': df_long
    }

    decorator.generate_report(anomalies, "Mock Strategy", "test.xlsx")

    # Verify inner report generator was called
    inner_report_generator.generate_report.assert_called_once_with(anomalies, "Mock Strategy", "test.xlsx")

    # Verify records were persisted
    assert repo_file.exists()

    with open(repo_file, 'r') as f:
        lines = f.readlines()

    assert len(lines) == 2
    record1 = json.loads(lines[0])
    record2 = json.loads(lines[1])

    assert record1['video_id'] == 'vid_short_1'
    assert record1['type'] == 'Shorts'

    assert record2['video_id'] == 'vid_long_1'
    assert record2['type'] == 'Long'

def test_file_anomaly_repository_error_handling(tmp_path):
    # Pass a directory instead of a file path to force an error
    repo = FileAnomalyRepository(str(tmp_path))

    anomaly = AnomalyRecord(
        video_id='vid_1',
        title='Test Video',
        views=100,
        retention_avg_pct=50.0,
        type='Shorts'
    )

    with pytest.raises(ArchivalError):
        repo.save(anomaly)
