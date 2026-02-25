import pytest
import asyncio
import pandas as pd
from unittest.mock import Mock, AsyncMock, MagicMock, call
from src.core.app import BachataAnalyticsApp
from src.core.models import VideoAnalysisInput

@pytest.fixture
def mock_ui():
    ui = Mock()
    # Mock loading context manager
    mock_cm = MagicMock()
    mock_cm.__enter__.return_value = mock_cm
    mock_cm.__exit__.return_value = None
    ui.loading.return_value = mock_cm

    # Mock async display_stream
    ui.display_stream = AsyncMock()
    return ui

@pytest.fixture
def mock_ai_service():
    service = Mock()
    service.analyze_semantics.return_value = "Test Analysis"
    return service

@pytest.fixture
def mock_report_generator():
    return Mock()

@pytest.fixture
def mock_data_ingestion_service():
    service = Mock()
    service.ingest_data.return_value = pd.DataFrame({
        'video_id': ['vid_1', 'vid_2'],
        'title': ['A', 'B'],
        'views': [100, 200],
        'retention_avg_pct': [50.0, 60.0],
        'type': ['Shorts', 'Long']
    })
    return service

@pytest.mark.asyncio
async def test_app_run_success(
    mock_ui, mock_ai_service, mock_report_generator, mock_data_ingestion_service
):
    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion_service
    )

    # Setup mock stream
    async def mock_stream(videos):
        yield "Chunk 1"
        yield "Chunk 2"

    # We must mock analyze_stream to return an async generator when called
    mock_ai_service.analyze_stream = Mock(side_effect=mock_stream)

    await app.run()

    # Verify interactions
    mock_data_ingestion_service.ingest_data.assert_called_once()
    mock_ui.display_header.assert_called()
    mock_ui.display_section.assert_called()
    mock_ui.display_table.assert_called()

    # Verify AI call
    mock_ai_service.analyze_stream.assert_called_once()

    # Verify stream display
    mock_ui.display_stream.assert_called_once()

    # Verify report generation
    mock_report_generator.generate_report.assert_called_once()
    mock_ui.display_success.assert_called()


@pytest.mark.asyncio
async def test_app_run_loading_persistence(
    mock_ui, mock_ai_service, mock_report_generator, mock_data_ingestion_service
):
    """
    Test that the loading indicator persists until the first chunk is received.
    """
    app = BachataAnalyticsApp(
        ui=mock_ui,
        ai_service=mock_ai_service,
        report_generator=mock_report_generator,
        data_ingestion_service=mock_data_ingestion_service
    )

    # Track call order
    call_order = []

    # Mock Generator
    # We need an async generator that logs when it yields
    async def mock_stream_gen(videos):
        call_order.append("stream_yield")
        yield "Chunk 1"

    mock_ai_service.analyze_stream = Mock(side_effect=mock_stream_gen)

    # Mock Loading Context Manager Exit
    original_exit = mock_ui.loading.return_value.__exit__

    def tracked_exit(exc_type, exc_val, exc_tb):
        call_order.append("loading_exit")
        return original_exit(exc_type, exc_val, exc_tb)

    mock_ui.loading.return_value.__exit__ = Mock(side_effect=tracked_exit)

    # Mock display_stream to consume the generator immediately
    async def mock_display_stream(gen):
        async for _ in gen:
            pass

    mock_ui.display_stream = AsyncMock(side_effect=mock_display_stream)

    # Run app
    await app.run()

    # With the bug: loading_exit happens immediately, then stream_yield happens inside display_stream
    # Expected with fix: stream_yield happens (for first chunk), then loading_exit happens.

    # Wait, stream_yield happens inside display_stream.
    # If we fetch first chunk inside loading block: stream_yield happens, THEN loading_exit happens.
    # Then display_stream is called with remaining chunks (or reconstructed stream).

    # So we expect "stream_yield" BEFORE "loading_exit".

    try:
            # Filter out the first loading_exit which comes from ingest_data
            # We want to verify the order for the analyze_stream call
            # Buggy order: [..., loading_exit, stream_yield, ...] (loading exits before yield)
            # Fixed order: [..., stream_yield, loading_exit, ...] (yields inside loading context)

            # Find all indices
            yield_indices = [i for i, x in enumerate(call_order) if x == "stream_yield"]
            exit_indices = [i for i, x in enumerate(call_order) if x == "loading_exit"]

            if not yield_indices:
                 pytest.fail(f"stream_yield not found in {call_order}")

            first_yield = yield_indices[0]

            # Find the first exit that occurs AFTER the yield
            # In the fixed version, the exit for the stream context should be immediately after yield (ignoring other logs)
            # In the buggy version, the exit for the stream context happened BEFORE the yield.

            # Let's look at the exit immediately PRECEDING the yield.
            # If the exit immediately preceding the yield corresponds to the stream context, that's a bug.
            # But we can't distinguish contexts easily here.

            # However, we know Ingestion happens first. So exit_indices[0] is Ingestion.
            # The next exit should be Stream.

            if len(exit_indices) < 2:
                 pytest.fail(f"Expected at least 2 loading exits (Ingest, Stream), found {len(exit_indices)}. Order: {call_order}")

            stream_exit_index = exit_indices[1]

            assert first_yield < stream_exit_index, f"Expected stream yield before stream loading exit. Order: {call_order}"

    except ValueError:
        pytest.fail(f"Missing expected calls. Order: {call_order}")
