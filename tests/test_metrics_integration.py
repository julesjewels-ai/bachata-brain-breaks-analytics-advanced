import os
import json
import pytest
import pandas as pd
from unittest.mock import Mock
from src.core.metrics import (
    FileMetricsRepository, StandardMetricsService,
    MetricsDataIngestionService, MetricsReportGenerator
)


@pytest.fixture
def temp_metrics_file(tmp_path):
    return str(tmp_path / "test_metrics.jsonl")


@pytest.fixture
def temp_export_file(tmp_path):
    return str(tmp_path / "test_export.json")


def test_metrics_integration_flow(
        temp_metrics_file: str, temp_export_file: str) -> None:
    """
    Tests the full metrics pipeline:
    Decorator -> Service -> Repository -> Export.
    """
    # 1. Setup Data
    mock_df = pd.DataFrame({
        'video_id': ['vid_1', 'vid_2'],
        'title': ['Test 1', 'Test 2'],
        'views': [100, 200],
        'retention_avg_pct': [50.0, 60.0],
        'type': ['Shorts', 'Long']
    })

    # 2. Setup Mocks
    mock_ingestion = Mock()
    mock_ingestion.ingest_data.return_value = mock_df

    mock_report = Mock()

    # 3. Setup Metrics Layer
    repo = FileMetricsRepository(filepath=temp_metrics_file)
    service = StandardMetricsService(repository=repo)

    decorated_ingestion = MetricsDataIngestionService(
        inner_service=mock_ingestion, metrics_service=service
    )
    decorated_report = MetricsReportGenerator(
        inner_generator=mock_report, metrics_service=service
    )

    # 4. Execute Flow
    df_result = decorated_ingestion.ingest_data()
    assert len(df_result) == 2

    decorated_report.generate_report(
        anomalies={"Shorts": mock_df},
        strategy="Test Strategy",
        filepath="test.xlsx"
    )

    # 5. Export
    service.export(temp_export_file)

    # 6. Verify Exported Data
    assert os.path.exists(temp_export_file)
    with open(temp_export_file, 'r') as f:
        exported_data = json.load(f)

    # We expect 3 metric events:
    # - ingestion_duration_seconds
    # - ingestion_row_count
    # - report_generation_duration_seconds
    assert len(exported_data) == 3

    metric_names = [event['metric_name'] for event in exported_data]
    assert "ingestion_duration_seconds" in metric_names
    assert "ingestion_row_count" in metric_names
    assert "report_generation_duration_seconds" in metric_names

    # Specific assertions on the row count
    row_count_event = next(
        e for e in exported_data if e['metric_name'] == 'ingestion_row_count')
    assert row_count_event['value'] == 2.0
    assert row_count_event['unit'] == 'rows'
