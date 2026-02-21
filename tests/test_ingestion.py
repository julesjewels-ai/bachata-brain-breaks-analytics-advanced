"""
Unit tests for data ingestion services.
"""
import pandas as pd
from src.core.ingestion import SimulationDataIngestionService

def test_simulation_data_ingestion():
    """Test that simulation ingestion returns valid data."""
    service = SimulationDataIngestionService()
    df = service.ingest_data()

    assert isinstance(df, pd.DataFrame)
    assert not df.empty

    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert list(df.columns) == expected_cols

    # Verify data types and constraints
    assert df['views'].min() >= 0
    assert df['retention_avg_pct'].min() >= 0.0
    assert df['retention_avg_pct'].max() <= 100.0
