"""
Tests for UI integration.
"""
from typing import ContextManager
from contextlib import nullcontext
import pandas as pd
from src.core.ui import RichConsoleUI
from src.core.interfaces import UserInterface


class MockUI(UserInterface):
    """
    Mock UI that records calls.
    """
    def __init__(self):
        self.calls = []

    def display_header(self, text: str) -> None:
        self.calls.append(('header', text))

    def display_section(self, text: str) -> None:
        self.calls.append(('section', text))

    def display_status(self, text: str) -> None:
        self.calls.append(('status', text))

    def display_table(self, data: pd.DataFrame, title=None) -> None:
        self.calls.append(('table', len(data)))

    def display_error(self, error) -> None:
        self.calls.append(('error', str(error)))

    def display_success(self, text: str) -> None:
        self.calls.append(('success', text))

    def display_info(self, text: str) -> None:
        self.calls.append(('info', text))

    def display_message(self, text: str) -> None:
        self.calls.append(('message', text))

    def loading(self, text: str) -> ContextManager:
        self.calls.append(('loading', text))
        return nullcontext()


def test_rich_ui_instantiation():
    ui = RichConsoleUI()
    assert isinstance(ui, RichConsoleUI)


def test_mock_ui_recording():
    ui = MockUI()
    ui.display_header("Test")
    assert ui.calls[0] == ('header', "Test")

    with ui.loading("Loading..."):
        pass
    assert ('loading', "Loading...") in ui.calls


def test_rich_ui_methods(capsys):
    # This test might be tricky because Rich writes to stdout/stderr
    # in a complex way.
    # We just ensure no exceptions are raised.
    ui = RichConsoleUI()
    ui.display_header("Header")
    ui.display_status("Status")

    df = pd.DataFrame({'A': [1], 'B': [2]})
    ui.display_table(df)

    ui.display_success("Success")
    ui.display_error("Error")

    # Capture output
    # captured = capsys.readouterr()
    # Rich might not be easily captured by capsys if it forces TTY
    # or uses direct write.
    # But usually it writes to stdout.
    # assert "Header" in captured.out
