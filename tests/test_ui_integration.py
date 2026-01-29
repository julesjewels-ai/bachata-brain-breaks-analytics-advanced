import pandas as pd
from typing import Union, Optional
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


def test_app_integration_with_ui():
    ui = MockUI()
    app = BachataAnalyticsApp(ui=ui)

    # Run the app (mocking ingestion/processing implicitly by the app's design which mocks data internally)
    app.run()

    # Verify sequence of calls
    assert any(c[0] == 'header' and "Bachata Analytics Dashboard" in c[1]
               for c in ui.calls)
    assert any(c[0] == 'success' and "Data loaded" in c[1] for c in ui.calls)
    assert any(c[0] == 'section' and "Viral Anomalies" in c[1]
               for c in ui.calls)
    assert any(c[0] == 'table' for c in ui.calls)
    assert any(c[0] == 'section' and "Gemini 3 Agent Analysis" in c[1]
               for c in ui.calls)
    assert any(c[0] == 'info' for c in ui.calls)  # Strategy
    assert any(c[0] == 'status' and "Generating Excel Report" in c[1]
               for c in ui.calls)
    assert any(c[0] == 'success' and "Report saved" in c[1] for c in ui.calls)
    assert any(c[0] == 'success' and "Dashboard update complete" in c[1]
               for c in ui.calls)
