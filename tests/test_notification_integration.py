"""
Integration tests for notifications.
"""
from unittest.mock import Mock, MagicMock
import pytest
import pandas as pd
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)


@pytest.mark.asyncio
async def test_app_sends_notifications():
    # Setup mocks
    # UserInterface must return a context manager for loading()
    mock_ui = Mock(spec=UserInterface)
    mock_ui.loading.return_value = MagicMock()

    mock_ai = Mock(spec=AIService)
    mock_report = Mock(spec=ReportGenerator)
    mock_ingest = Mock(spec=DataIngestionService)
    mock_notification = Mock(spec=NotificationService)

    # Setup return values
    # Ingest data must return a DataFrame
    mock_ingest.ingest_data.return_value = pd.DataFrame({
        'video_id': ['vid_1'],
        'title': ['Test'],
        'views': [100],
        'retention_avg_pct': [50.0],
        'type': ['Shorts']
    })

    # Configure loading context manager
    mock_ui.loading.return_value.__enter__.return_value = None

    # Mock async generator
    async def mock_stream(videos):
        yield "Strategy"

    mock_ai.analyze_stream.side_effect = mock_stream
    # Ensure UI display_stream is awaited
    mock_ui.display_stream = MagicMock()

    async def mock_display_stream(gen):
        async for _ in gen:
            pass
    mock_ui.display_stream.side_effect = mock_display_stream

    # Initialize app
    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai,
        report_generator=mock_report,
        data_ingestion_service=mock_ingest,
        notification_service=mock_notification
    )

    # Run app
    await app.run()

    # Verify notifications were sent
    assert mock_notification.notify.called

    # Check specific notifications
    # 1. Ingestion success
    # 2. Report Generation success
    # 3. Complete
    assert mock_notification.notify.call_count >= 3

    # Check specific notifications using any
    calls = mock_notification.notify.call_args_list

    # Check if 'Ingestion' notification was sent
    assert any(
        c[0][0].title == "Ingestion" and c[0][0].level == 'success'
        for c in calls
    )

    # Check if 'Complete' notification was sent
    assert any(
        c[0][0].title == "Complete" and c[0][0].level == 'success'
        for c in calls
    )
