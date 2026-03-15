"""
Integration tests for core application logic.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, patch
from src.core.app import BachataAnalyticsApp
from src.core.models import VideoAnalysisInput
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)

@pytest.fixture
def mock_ui():
    return Mock(spec=UserInterface)

@pytest.fixture
def mock_ai_service():
    return Mock(spec=AIService)

@pytest.fixture
def mock_report_generator():
    return Mock(spec=ReportGenerator)

@pytest.fixture
def mock_data_ingestion_service():
    return Mock(spec=DataIngestionService)

@pytest.fixture
def mock_notification_service():
    return Mock(spec=NotificationService)

@pytest.fixture
def app(mock_ui, mock_ai_service, mock_report_generator, mock_data_ingestion_service, mock_notification_service):
    # Mock AppConfig to avoid env issues
    with patch('src.core.app.AppConfig.get_config') as mock_get_config:
        mock_get_config.return_value = Mock()
        return BachataAnalyticsApp(
            ui=mock_ui,
            ai_service=mock_ai_service,
            report_generator=mock_report_generator,
            data_ingestion_service=mock_data_ingestion_service,
            notification_service=mock_notification_service
        )

def test_agent_initialization(app):
    assert app.ai_service is not None
    assert app.ui is not None
    assert app.report_generator is not None
    assert app.data_ingestion_service is not None
    assert app.notification_service is not None

@pytest.mark.asyncio
async def test_ingest_data_structure(app, mock_data_ingestion_service, mock_ui):
    # Mock context manager for loading
    mock_ui.loading.return_value.__enter__ = Mock()
    mock_ui.loading.return_value.__exit__ = Mock()

    expected_df = pd.DataFrame({
        'video_id': ['1'], 'title': ['A'], 'views': [100], 'retention_avg_pct': [50], 'type': ['Shorts']
    })
    mock_data_ingestion_service.ingest_data.return_value = expected_df

    df = await app.ingest_data()
    expected_cols = ['video_id', 'title', 'views', 'retention_avg_pct', 'type']
    assert not df.empty
    assert list(df.columns) == expected_cols

def test_outlier_detection(app):
    df = pd.DataFrame({
        'video_id': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11'],
        'title': ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'Viral'],
        'views': [100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 10000],
        'retention_avg_pct': [50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 90],
        'type': ['Shorts'] * 11
    })
    anomalies = app.detect_outliers(df)
    assert 'Shorts' in anomalies
    assert isinstance(anomalies['Shorts'], pd.DataFrame)
    assert 'Viral' in anomalies['Shorts']['title'].values

def test_outlier_detection_dynamic_types(app):
    """Test that outlier detection handles arbitrary types dynamically."""
    df = pd.DataFrame({
        'video_id': ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15', '16', '17', '18', '19', '20', '21', '22'],
        'title': ['A']*10 + ['B'] + ['C']*10 + ['D'],
        'views': [100]*10 + [1000] + [100]*10 + [1000],
        'retention_avg_pct': [50]*10 + [90] + [50]*10 + [90],
        'type': ['NewType1']*11 + ['NewType2']*11
    })
    anomalies = app.detect_outliers(df)
    assert 'NewType1' in anomalies
    assert 'NewType2' in anomalies
    assert len(anomalies['NewType1']) == 1  # 1000 should be filtered
    assert len(anomalies['NewType2']) == 1

def test_prepare_agent_input(app):
    df = pd.DataFrame({
        'video_id': [str(i) for i in range(12)],
        'title': [f'Title {i}' for i in range(12)],
        'views': [100 * i for i in range(12)],
        'retention_avg_pct': [10 + i for i in range(12)],
        'type': ['Shorts'] * 12
    })

    result = app._prepare_agent_input(df)

    # Check return type
    assert isinstance(result, list)
    assert all(isinstance(x, VideoAnalysisInput) for x in result)

    # 5 top, 5 bottom = 10 total
    assert len(result) == 10
