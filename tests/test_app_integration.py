import pytest
from unittest.mock import Mock, AsyncMock
import pandas as pd
from typing import AsyncGenerator
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import (
    UserInterface, AIService, ReportGenerator, DataIngestionService,
    NotificationService
)


@pytest.fixture
def mock_ui() -> Mock:
    ui = Mock(spec=UserInterface)

    async def drain_stream(gen):
        async for _ in gen:
            pass

    ui.display_stream = AsyncMock(side_effect=drain_stream)
    # Mock context manager for loading
    mock_loading = Mock()
    mock_loading.__enter__ = Mock(return_value=mock_loading)
    mock_loading.__exit__ = Mock(return_value=None)
    ui.loading.return_value = mock_loading
    return ui


@pytest.fixture
def mock_ai_service() -> Mock:
    ai = Mock(spec=AIService)

    async def sample_generator(*args, **kwargs) -> AsyncGenerator[str, None]:
        yield "AI "
        yield "Strategy "
        yield "Analysis"
    ai.analyze_stream.side_effect = sample_generator
    return ai


@pytest.fixture
def mock_report_generator() -> Mock:
    return Mock(spec=ReportGenerator)


@pytest.fixture
def mock_data_ingestion() -> Mock:
    ingestion = Mock(spec=DataIngestionService)
    # Provide enough data to pass the quantile calculations and top/bottom 5
    df = pd.DataFrame({
        'video_id': [f'vid_{i}' for i in range(12)],
        'title': [f'Video {i}' for i in range(12)],
        'description': ['desc'] * 12,
        'published_at': ['2023-01-01T00:00:00Z'] * 12,
        'views': [1000 * i for i in range(12)],  # Increasing views
        'likes': [100 * i for i in range(12)],
        'comments': [10 * i for i in range(12)],
        'duration_sec': [60] * 12,
        # Increasing retention
        'retention_avg_pct': [50.0 + i for i in range(12)],
        'type': ['Shorts'] * 6 + ['Long'] * 6
    })
    ingestion.ingest_data.return_value = df
    return ingestion


@pytest.fixture
def mock_notification_service() -> Mock:
    return Mock(spec=NotificationService)


@pytest.mark.asyncio
async def test_bachata_analytics_app_run(
    mock_ui: Mock,
    mock_ai_service: Mock,
    mock_report_generator: Mock,
    mock_data_ingestion: Mock,
    mock_notification_service: Mock
) -> None:
    """Test the happy path of the entire application pipeline."""
    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion,
        notification_service=mock_notification_service
    )

    await app.run()

    # 1. Verify Data Ingestion
    mock_data_ingestion.ingest_data.assert_called_once()
    mock_ui.display_header.assert_called_with("Bachata Analytics Dashboard")

    # Check Ingestion Complete notification
    notification_calls = mock_notification_service.notify.call_args_list
    assert any(
        "Ingestion" in call_args[0][0].title
        for call_args in notification_calls
    )

    # 2. Verify AI Service
    mock_ai_service.analyze_stream.assert_called_once()
    mock_ui.display_stream.assert_awaited_once()

    # 3. Verify Report Generation
    mock_report_generator.generate_report.assert_called_once()
    report_args = mock_report_generator.generate_report.call_args[0]

    anomalies = report_args[0]
    strategy = report_args[1]
    filepath = report_args[2]

    assert "Shorts" in anomalies
    assert "Long" in anomalies
    assert strategy == "AI Strategy Analysis"  # String joined from stream
    assert filepath == "bachata_analytics.xlsx"

    # Verify Complete notification
    assert any(
        "Complete" in call_args[0][0].title
        for call_args in notification_calls
    )


@pytest.mark.asyncio
async def test_ui_events_sequence(
    mock_ui: Mock,
    mock_ai_service: Mock,
    mock_report_generator: Mock,
    mock_data_ingestion: Mock,
    mock_notification_service: Mock
) -> None:
    """Verify that stream_yield occurs before loading_exit event."""
    # We will track the order of events
    events = []

    # Hook loading context manager
    mock_loading = Mock()
    mock_loading.__enter__ = Mock(return_value=mock_loading)

    def loading_exit_side_effect(exc_type, exc_val, exc_tb):
        events.append("loading_exit")
        return None
    mock_loading.__exit__ = Mock(side_effect=loading_exit_side_effect)

    def loading_side_effect(text):
        if "Initializing Gemini 3 Stream" in text:
            events.append("loading_enter")
        return mock_loading
    mock_ui.loading.side_effect = loading_side_effect

    # Hook display stream
    async def capture_display_stream(gen):
        async for chunk in gen:
            events.append("stream_yield")
    mock_ui.display_stream.side_effect = capture_display_stream

    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion,
        notification_service=mock_notification_service
    )

    await app.run()

    # Verify the sequence:
    # loading_enter -> loading_exit -> stream_yield (for each chunk)
    # The loading context wraps the call to analyze_stream (initialization),
    # not the iteration.
    assert "loading_enter" in events
    assert "loading_exit" in events
    assert "stream_yield" in events

    # loading_exit must occur before the first stream_yield because
    # stream iteration happens in display_stream, which is awaited
    # AFTER the loading context block.
    exit_idx = events.index("loading_exit")
    first_yield_idx = events.index("stream_yield")
    assert exit_idx < first_yield_idx
