import pytest
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
from src.core.app import BachataAnalyticsApp

@pytest.mark.asyncio
async def test_app_calls_notification_service(mocker):
    # Mock AppConfig to avoid environment issues
    mock_config_cls = mocker.patch("src.core.app.AppConfig")
    mock_config = MagicMock()
    mock_config_cls.get_config.return_value = mock_config

    # Mocks
    mock_ui = MagicMock()
    mock_ui.loading.return_value.__enter__.return_value = None
    mock_ui.display_stream = AsyncMock()

    mock_ai = MagicMock()

    # Mocking async generator correctly
    async def mock_stream(*args, **kwargs):
        yield "strategy"
    mock_ai.analyze_stream = mock_stream

    mock_report = MagicMock()

    mock_ingestion = MagicMock()
    # Mock DataFrame with required columns
    mock_ingestion.ingest_data.return_value = pd.DataFrame([
        {
            'video_id': 'vid_1', 'title': 'Title 1', 'views': 1000,
            'retention_avg_pct': 50.0, 'type': 'Long'
        },
        {
            'video_id': 'vid_2', 'title': 'Title 2', 'views': 2000,
            'retention_avg_pct': 60.0, 'type': 'Shorts'
        }
    ])

    mock_notification = MagicMock()

    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai,
        report_generator=mock_report,
        data_ingestion_service=mock_ingestion,
        notification_service=mock_notification
    )

    await app.run()

    # Assertions
    # Check if notify was called
    assert mock_notification.notify.call_count >= 2
    mock_notification.notify.assert_any_call("System", "Analytics pipeline started", "INFO")
    mock_notification.notify.assert_any_call("System", "Analytics pipeline completed", "SUCCESS")
    mock_notification.notify.assert_any_call("Ingestion", "Data loaded: 2 records", "INFO")
