"""
Unit tests for data ingestion services.
"""
import pandas as pd
from src.core.ingestion import SimulationDataIngestionService


def test_simulation_data_ingestion():
    service = SimulationDataIngestionService()
    df = service.ingest_data()

    assert not df.empty
    assert len(df) == 20
    expected_cols = [
        'video_id', 'title', 'views', 'retention_avg_pct', 'type'
    ]
    # Check if all expected columns are in the dataframe
    for col in expected_cols:
        assert col in df.columns

    # Check data types
    assert pd.api.types.is_string_dtype(df['video_id'])
    assert pd.api.types.is_string_dtype(df['title'])
    assert pd.api.types.is_integer_dtype(df['views'])
    assert pd.api.types.is_float_dtype(df['retention_avg_pct'])
    assert pd.api.types.is_string_dtype(df['type'])

    # Check value ranges
    assert df['views'].min() >= 500
    assert df['retention_avg_pct'].min() >= 20.0
    assert df['retention_avg_pct'].max() <= 100.0
    assert set(df['type'].unique()) == {'Long', 'Shorts'}
