"""
Unit tests for core application logic (UI Controller).
"""
import pytest
from unittest.mock import MagicMock
import pandas as pd
from src.core.app import BachataAnalyticsApp
from src.core.services import AnalyticsService

class DummyUI:
    def display_header(self, text: str): pass
    def display_section(self, text: str): pass
    def display_status(self, text: str): pass
    def display_table(self, data, title=None): pass
    def display_error(self, error): pass
    def display_success(self, text: str): pass
    def display_info(self, text: str): pass
    def display_message(self, text: str): pass

def test_app_initialization():
    app = BachataAnalyticsApp(ui=DummyUI())
    assert isinstance(app.service, AnalyticsService)

def test_app_run_flow():
    # Mock service
    mock_service = MagicMock(spec=AnalyticsService)
    mock_service.ingest_data.return_value = pd.DataFrame({
        'video_id': ['1'], 'title': ['A'], 'views': [100],
        'retention_avg_pct': [50], 'type': ['Shorts']
    })
    mock_service.detect_outliers.return_value = {
        'Shorts': pd.DataFrame({
            'title': ['A'],
            'views': [100],
            'retention_avg_pct': [50.0]
        })
    }
    mock_service.analyze_semantics.return_value = "Strategy"
    mock_service.generate_report.return_value = "report.xlsx"

    ui = DummyUI()
    app = BachataAnalyticsApp(ui=ui, service=mock_service)
    app.run()

    # Verify service calls
    mock_service.ingest_data.assert_called_once()
    mock_service.detect_outliers.assert_called_once()
    mock_service.analyze_semantics.assert_called_once()
    mock_service.generate_report.assert_called_once()
