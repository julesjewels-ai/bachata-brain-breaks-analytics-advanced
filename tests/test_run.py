import pytest
import pandas as pd
from unittest.mock import MagicMock, AsyncMock, call
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import UserInterface, AIService, ReportGenerator

@pytest.fixture
def mock_ui():
    ui = MagicMock(spec=UserInterface)
    ui.loading.return_value.__enter__.return_value = None
    ui.display_stream = AsyncMock()
    return ui

@pytest.fixture
def mock_ai_service():
    service = MagicMock(spec=AIService)
    async def mock_stream(data):
        yield "chunk1"
        yield "chunk2"
    service.analyze_stream.side_effect = mock_stream
    return service

@pytest.fixture
def mock_report_generator():
    return MagicMock(spec=ReportGenerator)

@pytest.mark.asyncio
async def test_run_success(mock_ui, mock_ai_service, mock_report_generator):
    app = BachataAnalyticsApp(mock_ui, mock_ai_service, mock_report_generator)

    # Mock ingest_data to return a small DataFrame
    app.ingest_data = MagicMock(return_value=pd.DataFrame({
        'video_id': ['vid_1', 'vid_2'],
        'title': ['A', 'B'],
        'views': [100, 200],
        'retention_avg_pct': [50.0, 60.0],
        'type': ['Shorts', 'Long']
    }))

    # Mock detect_outliers
    app.detect_outliers = MagicMock(return_value={
        'Shorts': pd.DataFrame({
            'video_id': ['vid_1'],
            'title': ['A'],
            'views': [100],
            'retention_avg_pct': [50.0],
            'type': ['Shorts']
        })
    })

    await app.run()

    # Verify calls
    assert app.ingest_data.called
    assert app.detect_outliers.called
    mock_ui.display_header.assert_called_with("Bachata Analytics Dashboard")
    mock_ui.display_section.assert_any_call("Viral Anomalies (Shorts)")
    mock_ui.display_section.assert_any_call("Gemini 3 Agent Analysis")
    assert mock_ai_service.analyze_stream.called
    assert mock_ui.display_stream.called
    mock_report_generator.generate_report.assert_called()
    mock_ui.display_success.assert_called_with("Dashboard update complete.")

@pytest.mark.asyncio
async def test_run_validation_error(mock_ui, mock_ai_service, mock_report_generator):
    app = BachataAnalyticsApp(mock_ui, mock_ai_service, mock_report_generator)

    # Mock ingest_data to return empty DF or something that causes validation error in _prepare_agent_input
    # However, _prepare_agent_input validates the data again.
    # To trigger the ValidationError in run(), we need _prepare_agent_input to raise it.

    app.ingest_data = MagicMock(return_value=pd.DataFrame({
        'video_id': ['1'],
        'title': ['A'],
        'views': [100],
        'retention_avg_pct': [50.0],
        'type': ['Shorts']
    }))

    # Mock _prepare_agent_input to raise ValidationError
    from pydantic import ValidationError
    # We need a dummy validation error.
    # It's hard to instantiate Pydantic ValidationError directly without model validation.
    # So we'll mock the method to raise it.

    # We can mock the Pydantic model validation inside _prepare_agent_input, but easier to mock the method itself.
    # But wait, we are testing `run`, so we should mock `_prepare_agent_input`.
    app._prepare_agent_input = MagicMock(side_effect=ValidationError.from_exception_data("TestError", []))

    await app.run()

    mock_ui.display_error.assert_called_with("Aborting analysis for security.")
    assert not mock_ai_service.analyze_stream.called
