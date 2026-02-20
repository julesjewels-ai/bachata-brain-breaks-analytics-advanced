import pytest
from unittest.mock import MagicMock, AsyncMock
import pandas as pd
from contextlib import contextmanager
from typing import AsyncGenerator

from src.core.app import BachataAnalyticsApp
from src.core.interfaces import UserInterface, AIService, ReportGenerator

class MockUI(UserInterface):
    def __init__(self):
        self.display_header_mock = MagicMock()
        self.display_success_mock = MagicMock()
        self.display_table_mock = MagicMock()
        self.display_section_mock = MagicMock()
        self.display_info_mock = MagicMock()
        self.display_error_mock = MagicMock()
        self.loading_mock = MagicMock()
        self.display_stream_mock = AsyncMock()

    def display_header(self, text: str):
        self.display_header_mock(text)

    def display_section(self, text: str):
        self.display_section_mock(text)

    def display_status(self, text: str):
        pass

    def display_table(self, data, title=None):
        self.display_table_mock(data, title)

    def display_error(self, error):
        self.display_error_mock(error)

    def display_success(self, text: str):
        self.display_success_mock(text)

    def display_info(self, text: str):
        self.display_info_mock(text)

    def display_message(self, text: str):
        pass

    def loading(self, text: str):
        self.loading_mock(text)
        @contextmanager
        def cm():
            yield
        return cm()

    async def display_stream(self, generator: AsyncGenerator[str, None]) -> None:
        await self.display_stream_mock(generator)
        # Crucial: Consume the generator to trigger the capture logic in the app
        async for _ in generator:
            pass

class MockAI(AIService):
    def analyze_semantics(self, videos):
        pass

    async def analyze_stream(self, videos):
        yield "chunk1"
        yield "chunk2"

class MockReportGen(ReportGenerator):
    def __init__(self):
        self.generate_report_mock = MagicMock()

    def generate_report(self, anomalies, strategy, filepath):
        self.generate_report_mock(anomalies, strategy, filepath)

@pytest.mark.asyncio
async def test_app_run_flow():
    ui = MockUI()
    ai = MockAI()
    report_gen = MockReportGen()

    app = BachataAnalyticsApp(ui, ai, report_gen)

    # Mock internal methods to isolate run logic
    df_mock = pd.DataFrame({
        'video_id': ['vid_1'],
        'title': ['Test'],
        'views': [1000],
        'retention_avg_pct': [50.0],
        'type': ['Shorts']
    })

    app.ingest_data = MagicMock(return_value=df_mock)

    anomalies_mock = {'Shorts': df_mock}
    app.detect_outliers = MagicMock(return_value=anomalies_mock)

    app._prepare_agent_input = MagicMock(return_value=[])

    # Run the app
    await app.run()

    # Assertions
    ui.display_header_mock.assert_called_with("Bachata Analytics Dashboard")
    app.ingest_data.assert_called_once()
    app.detect_outliers.assert_called_once_with(df_mock)

    # Check if display_table was called for anomalies
    assert ui.display_table_mock.call_count >= 1

    # Check Report Generation
    # Strategy should be "chunk1chunk2"
    report_gen.generate_report_mock.assert_called_once()
    args, _ = report_gen.generate_report_mock.call_args
    assert args[0] == anomalies_mock # anomalies
    assert args[1] == "chunk1chunk2" # strategy
    assert args[2] == "bachata_analytics.xlsx" # filepath
