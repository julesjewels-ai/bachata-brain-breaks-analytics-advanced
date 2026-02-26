"""
Integration tests for Notification Service within the App.
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import pandas as pd

from src.core.app import BachataAnalyticsApp
from src.core.models import NotificationEvent, VideoAnalysisInput
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService, NotificationService
)

@pytest.fixture
def mock_ui():
    ui = Mock(spec=UserInterface)
    # Correctly mock context manager
    context_manager = Mock()
    context_manager.__enter__ = Mock(return_value=ui)
    context_manager.__exit__ = Mock(return_value=None)
    ui.loading.return_value = context_manager
    # AsyncMock for display_stream
    ui.display_stream = AsyncMock()
    return ui

@pytest.fixture
def mock_ai_service():
    service = Mock(spec=AIService)
    service.analyze_semantics.return_value = "Analysis"
    async def stream(videos):
        yield "Chunk"
    service.analyze_stream.side_effect = stream
    return service

@pytest.fixture
def mock_report_generator():
    return Mock(spec=ReportGenerator)

@pytest.fixture
def mock_data_ingestion_service():
    service = Mock(spec=DataIngestionService)
    # Return a DataFrame with required columns
    service.ingest_data.return_value = pd.DataFrame({
        'video_id': ['vid_1'],
        'title': ['Test Video'],
        'views': [1000],
        'retention_avg_pct': [80.0],
        'type': ['Long']
    })
    return service

@pytest.fixture
def mock_notification_service():
    return Mock(spec=NotificationService)

@pytest.mark.asyncio
async def test_app_triggers_notifications(
    mock_ui,
    mock_ai_service,
    mock_report_generator,
    mock_data_ingestion_service,
    mock_notification_service
):
    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion_service,
        notification_service=mock_notification_service
    )

    await app.run()

    # Verify notifications
    assert mock_notification_service.notify.call_count >= 2

    calls = mock_notification_service.notify.call_args_list

    # Check for Data Ingestion success
    ingestion_call = calls[0]
    event = ingestion_call[0][0]
    assert isinstance(event, NotificationEvent)
    assert event.title == "Data Ingestion"
    assert event.level == "INFO"

    # Check for Report Generation success
    report_call = calls[-1]
    event = report_call[0][0]
    assert event.title == "Report Generated"
    assert event.level == "SUCCESS"

@pytest.mark.asyncio
async def test_app_triggers_error_notification(
    mock_ui,
    mock_ai_service,
    mock_report_generator,
    mock_data_ingestion_service,
    mock_notification_service
):
    # Simulate validation error
    mock_data_ingestion_service.ingest_data.return_value = pd.DataFrame({
        'video_id': ['invalid_id'], # pattern mismatch
        'title': ['Test'],
        'views': [100],
        'retention_avg_pct': [50.0],
        'type': ['Long']
    })

    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion_service,
        notification_service=mock_notification_service
    )

    await app.run()

    # Should trigger validation error notification
    # Find call with Validation Error
    found = False
    for call_args in mock_notification_service.notify.call_args_list:
        event = call_args[0][0]
        if event.title == "Validation Error" and event.level == "ERROR":
            found = True
            break

    assert found
