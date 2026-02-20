import asyncio
import pandas as pd
from typing import Union, Optional, ContextManager, Any, AsyncGenerator
from contextlib import nullcontext
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import UserInterface, AIService, ReportGenerator, DataIngestionService

class MockReportGenerator(ReportGenerator):
    def generate_report(self, anomalies, strategy, filepath):
        pass

class MockUI(UserInterface):
    def __init__(self):
        self.calls = []

    def display_header(self, text: str) -> None:
        self.calls.append(('header', text))

    def display_section(self, text: str) -> None:
        self.calls.append(('section', text))

    def display_status(self, text: str) -> None:
        self.calls.append(('status', text))

    def display_table(self, data: pd.DataFrame, title: Optional[str] = None) -> None:
        self.calls.append(('table', data, title))

    def display_error(self, error: Union[Exception, str]) -> None:
        self.calls.append(('error', error))

    def display_success(self, text: str) -> None:
        self.calls.append(('success', text))

    def display_info(self, text: str) -> None:
        self.calls.append(('info', text))

    def display_message(self, text: str) -> None:
        self.calls.append(('message', text))

    def loading(self, text: str) -> ContextManager[Any]:
        self.calls.append(('loading', text))
        return nullcontext()

    async def display_stream(self, generator: AsyncGenerator[str, None]) -> None:
        self.calls.append(('stream_start',))
        async for chunk in generator:
             self.calls.append(('stream_chunk', chunk))

class MockAIService(AIService):
    def analyze_semantics(self, videos):
        return "Mock Analysis Strategy"
    async def analyze_stream(self, videos):
        yield "Mock Analysis Strategy"

class MockDataIngestionService(DataIngestionService):
    def ingest_data(self) -> pd.DataFrame:
        return pd.DataFrame([
            {'video_id': 'vid_1', 'title': 'Normal', 'views': 100, 'retention_avg_pct': 50.0, 'type': 'Shorts'},
            {'video_id': 'vid_2', 'title': 'Viral', 'views': 1000, 'retention_avg_pct': 90.0, 'type': 'Shorts'},
        ])

def test_app_integration_with_ui():
    ui = MockUI()
    ai_service = MockAIService()
    report_generator = MockReportGenerator()
    ingestion_service = MockDataIngestionService()
    app = BachataAnalyticsApp(ui=ui, ai_service=ai_service, report_generator=report_generator, data_ingestion_service=ingestion_service)

    # Run the app
    asyncio.run(app.run())

    # Verify sequence of calls
    assert any(c[0] == 'header' and "Bachata Analytics Dashboard" in c[1] for c in ui.calls)
    assert any(c[0] == 'success' and "Data loaded" in c[1] for c in ui.calls)
    assert any(c[0] == 'section' and "Viral Anomalies" in c[1] for c in ui.calls)
    assert any(c[0] == 'table' for c in ui.calls)
    assert any(c[0] == 'section' and "Gemini 3 Agent Analysis" in c[1] for c in ui.calls)

    # Check for stream calls
    assert any(c[0] == 'stream_start' for c in ui.calls)
    assert any(c[0] == 'stream_chunk' and "Mock Analysis Strategy" in c[1] for c in ui.calls)

    assert any(c[0] == 'loading' and "Generating Excel Report" in c[1] for c in ui.calls)
    assert any(c[0] == 'success' and "Report saved" in c[1] for c in ui.calls)
    assert any(c[0] == 'success' and "Dashboard update complete" in c[1] for c in ui.calls)
