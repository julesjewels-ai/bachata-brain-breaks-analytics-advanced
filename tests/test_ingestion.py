"""
Unit tests for data ingestion services.
"""
import pytest
import pandas as pd
from unittest.mock import Mock
from src.core.ingestion import SimulationDataIngestionService
from src.core.interfaces import UserInterface


class TestSimulationDataIngestionService:
    @pytest.fixture
    def mock_ui(self):
        ui = Mock(spec=UserInterface)
        # Mock context manager for loading
        ui.loading.return_value.__enter__ = Mock()
        ui.loading.return_value.__exit__ = Mock()
        return ui

    def test_ingest_data_returns_dataframe(self, mock_ui):
        service = SimulationDataIngestionService(ui=mock_ui)
        df = service.ingest_data()

        assert isinstance(df, pd.DataFrame)
        assert not df.empty
        assert 'video_id' in df.columns
        assert 'title' in df.columns
        assert 'views' in df.columns
        assert 'retention_avg_pct' in df.columns
        assert 'type' in df.columns

    def test_ingest_data_calls_loading(self, mock_ui):
        service = SimulationDataIngestionService(ui=mock_ui)
        service.ingest_data()

        mock_ui.loading.assert_called_once_with("Ingesting channel data...")

    def test_ingest_data_validates_rows(self, mock_ui):
        service = SimulationDataIngestionService(ui=mock_ui)
        df = service.ingest_data()

        # Check that we have valid data (basic check based on simulation logic)
        assert df['views'].min() >= 500
        assert df['retention_avg_pct'].min() >= 20.0
        assert df['retention_avg_pct'].max() <= 100.0
