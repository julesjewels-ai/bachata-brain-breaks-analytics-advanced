"""
Integration tests for NotificationService within BachataAnalyticsApp.
"""
import pytest
import pandas as pd
from unittest.mock import Mock, AsyncMock
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)


@pytest.fixture
def mock_ui():
    ui = Mock(spec=UserInterface)
    # Mocking context manager properly
    mock_loading_context = Mock()
    mock_loading_context.__enter__ = Mock(return_value=None)
    mock_loading_context.__exit__ = Mock(return_value=None)
    ui.loading.return_value = mock_loading_context
    ui.display_stream = AsyncMock()
    return ui


@pytest.fixture
def mock_ai_service():
    ai = Mock(spec=AIService)
    ai.analyze_stream.return_value = AsyncMock()  # Mock the generator later
    return ai


@pytest.fixture
def mock_report_generator():
    return Mock(spec=ReportGenerator)


@pytest.fixture
def mock_data_ingestion():
    return Mock(spec=DataIngestionService)


@pytest.fixture
def mock_notification_service():
    return Mock(spec=NotificationService)


@pytest.mark.asyncio
async def test_app_run_lifecycle_notifications(
    mock_ui,
    mock_ai_service,
    mock_report_generator,
    mock_data_ingestion,
    mock_notification_service
):
    # Setup happy path data
    mock_data_ingestion.ingest_data.return_value = pd.DataFrame([
        {
            "video_id": "vid_1",
            "title": "A",
            "views": 1000,
            "retention_avg_pct": 50.0,
            "type": "Long"
        }
    ])

    # Mock AI stream (Async Generator)
    async def mock_stream_gen(videos):
        yield "AI Analysis"

    mock_ai_service.analyze_stream.side_effect = mock_stream_gen

    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion,
        notification_service=mock_notification_service
    )

    await app.run()

    # Extract all sent notifications
    calls = mock_notification_service.send.call_args_list
    # calls structure: [call(NotificationEvent(...)), ...]
    # Access arg 0 (event)
    events = [c[0][0] for c in calls]
    titles = [e.title for e in events]

    # Assertions for lifecycle events
    assert "Application Start" in titles
    assert "Ingestion Started" in titles
    assert "Ingestion Complete" in titles
    assert "Analysis" in titles
    # Depending on impl logic, might appear twice or once
    assert "AI Analysis" in titles
    assert "Reporting" in titles
    assert "Application End" in titles


@pytest.mark.asyncio
async def test_app_run_error_notification(
    mock_ui,
    mock_ai_service,
    mock_report_generator,
    mock_data_ingestion,
    mock_notification_service
):
    # Simulate critical failure during ingestion
    mock_data_ingestion.ingest_data.side_effect = Exception("Database Down")

    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion,
        notification_service=mock_notification_service
    )

    # App catches exception and logs critical error
    await app.run()

    # Check for Error Notification
    calls = mock_notification_service.send.call_args_list
    events = [c[0][0] for c in calls]
    error_events = [e for e in events if e.level == 'ERROR']

    assert len(error_events) >= 1
    last_error = error_events[-1]
    assert "Critical Error" == last_error.title
    assert "Database Down" in last_error.message
