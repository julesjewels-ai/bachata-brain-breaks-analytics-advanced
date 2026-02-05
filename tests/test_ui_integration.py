import asyncio
import pandas as pd
from typing import Union, Optional, ContextManager, Any, AsyncGenerator
from contextlib import nullcontext
from src.core.app import BachataAnalyticsApp


class MockUI:
    def __init__(self):
        self.calls = []

    def display_header(self, text: str) -> None:
        self.calls.append(('header', text))

    def display_section(self, text: str) -> None:
        self.calls.append(('section', text))

    def display_status(self, text: str) -> None:
        self.calls.append(('status', text))

    def display_table(
            self, data: pd.DataFrame,
            title: Optional[str] = None) -> None:
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

    async def display_stream(
            self,
            generator: AsyncGenerator[str, None]) -> None:
        self.calls.append(('stream_start',))
        async for chunk in generator:
            self.calls.append(('stream_chunk', chunk))


class MockAIService:
    def analyze_semantics(self, videos):
        return "Mock Analysis Strategy"

    async def analyze_stream(self, videos):
        yield "Mock Analysis Strategy"


def test_app_integration_with_ui():
    ui = MockUI()
    ai_service = MockAIService()
    app = BachataAnalyticsApp(ui=ui, ai_service=ai_service)

    # Run the app (mocking ingestion/processing implicitly by the app's design
    # which mocks data internally)
    asyncio.run(app.run())

    # Verify sequence of calls
    assert any(
        c[0] == 'header' and "Bachata Analytics Dashboard" in c[1]
        for c in ui.calls
    )
    assert any(
        c[0] == 'success' and "Data loaded" in c[1] for c in ui.calls
    )
    assert any(
        c[0] == 'section' and "Viral Anomalies" in c[1]
        for c in ui.calls
    )
    assert any(c[0] == 'table' for c in ui.calls)
    assert any(
        c[0] == 'section' and "Gemini 3 Agent Analysis" in c[1]
        for c in ui.calls
    )

    # Check for stream calls
    assert any(c[0] == 'stream_start' for c in ui.calls)
    assert any(
        c[0] == 'stream_chunk' and "Mock Analysis Strategy" in c[1]
        for c in ui.calls
    )

    # We NO LONGER expect 'info' with strategy because we stream it
    # assert any(c[0] == 'info' for c in ui.calls)

    assert any(
        c[0] == 'loading' and "Generating Excel Report" in c[1]
        for c in ui.calls
    )
    assert any(
        c[0] == 'success' and "Report saved" in c[1] for c in ui.calls
    )
    assert any(
        c[0] == 'success' and "Dashboard update complete" in c[1]
        for c in ui.calls
    )
