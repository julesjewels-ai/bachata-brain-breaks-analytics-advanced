"""
Tests for data ingestion.
"""
import pandas as pd
from src.core.ingestion import SimulationDataIngestionService
from src.core.models import VideoAnalysisInput

def test_simulation_data_structure():
    service = SimulationDataIngestionService()
    df = service.fetch_data()
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert not df.empty
    assert list(df.columns) == expected_cols
    assert len(df) == 20

def test_data_validation():
    service = SimulationDataIngestionService()
    df = service.fetch_data()

    # Check if all records are valid VideoAnalysisInput
    records = df.to_dict('records')
    for record in records:
        # This should not raise ValidationError
        VideoAnalysisInput(**record)
