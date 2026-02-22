"""
Tests for data ingestion.
"""
import pandas as pd
from unittest.mock import Mock
from contextlib import nullcontext
from src.core.ingestion import SimulationDataIngestionService
from src.core.interfaces import UserInterface

def test_simulation_data_ingestion():
    # Setup
    mock_ui = Mock(spec=UserInterface)
    mock_ui.loading.return_value = nullcontext()

    service = SimulationDataIngestionService(ui=mock_ui)

    # Execute
    df = service.ingest_data()

    # Verify
    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert list(df.columns) == expected_cols

    # Verify interaction
    mock_ui.loading.assert_called_once_with("Ingesting channel data...")

def test_data_validation_constraints():
    """Ensure generated data adheres to expected constraints."""
    mock_ui = Mock(spec=UserInterface)
    mock_ui.loading.return_value = nullcontext()

    service = SimulationDataIngestionService(ui=mock_ui)
    df = service.ingest_data()

    assert df['views'].min() >= 500
    assert df['views'].max() <= 500000
    assert df['retention_avg_pct'].min() >= 20.0
    assert df['retention_avg_pct'].max() <= 95.0
    assert set(df['type'].unique()).issubset({'Long', 'Shorts'})
