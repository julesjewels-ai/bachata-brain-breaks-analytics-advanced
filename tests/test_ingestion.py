"""
Unit tests for data ingestion services.
"""
import pytest
import pandas as pd
from src.core.ingestion import SimulationDataIngestionService
from src.core.models import VideoAnalysisInput

def test_simulation_data_ingestion():
    service = SimulationDataIngestionService()
    df = service.ingest_data()

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    assert len(df) == 20

    expected_columns = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert list(df.columns) == expected_columns

    # Verify data types indirectly via VideoAnalysisInput validation which happens during ingestion
    # But let's check some values
    assert df['video_id'].str.startswith('vid_').all()
    assert df['views'].min() >= 500
    assert df['retention_avg_pct'].min() >= 20.0
    assert df['retention_avg_pct'].max() <= 95.0
    assert df['type'].isin(['Shorts', 'Long']).all()
