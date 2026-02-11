import pytest
import pandas as pd
import asyncio
from unittest.mock import MagicMock
from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from typing import Any, AsyncGenerator

from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console(mocker: Any) -> MagicMock:
    return mocker.Mock(spec=Console)

@pytest.fixture
def ui(mock_console: MagicMock) -> RichConsoleUI:
    ui_instance = RichConsoleUI()
    ui_instance.console = mock_console
    return ui_instance

def test_display_table_empty(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    """Test display_table with an empty DataFrame."""
    df = pd.DataFrame()
    ui.display_table(df)

    mock_console.print.assert_called_once()
    args, _ = mock_console.print.call_args
    assert "[italic dim]No data available.[/italic dim]" in str(args[0])

@pytest.mark.parametrize("columns, data, expected_justification, expected_style", [
    # Standard string column
    (["Name"], [["Alice"], ["Bob"]], ["left"], ["cyan"]),
    # Numeric column (should be right-aligned and green)
    (["Age"], [[30], [25]], ["right"], ["green"]),
    # Specific column name "Views" (should be right-aligned and green)
    (["Views"], [[100], [200]], ["right"], ["green"]),
    # Specific column name "Retention" (should be right-aligned and green)
    (["Retention"], [[0.5], [0.6]], ["right"], ["green"]),
    # Specific column name "Retention (%)" (should be right-aligned and green)
    (["Retention (%)"], [[50.0], [60.0]], ["right"], ["green"]),
])
def test_display_table_columns_formatting(
    ui: RichConsoleUI,
    mock_console: MagicMock,
    columns: list[str],
    data: list[list[Any]],
    expected_justification: list[str],
    expected_style: list[str]
) -> None:
    """Test display_table column formatting logic."""
    df = pd.DataFrame(data, columns=columns)
    ui.display_table(df)

    mock_console.print.assert_called_once()
    args, _ = mock_console.print.call_args
    table = args[0]

    assert isinstance(table, Table)
    assert len(table.columns) == len(columns)

    for i, col in enumerate(table.columns):
        assert col.header == columns[i]
        assert col.justify == expected_justification[i]
        assert col.style == expected_style[i]

def test_display_table_rows(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    """Test display_table row addition and value conversion."""
    df = pd.DataFrame({
        "Name": ["Alice", "Bob"],
        "Age": [30, 25],
        "Score": [None, 95.5]
    })

    ui.display_table(df, title="Test Table")

    mock_console.print.assert_called_once()
    args, _ = mock_console.print.call_args
    table = args[0]

    assert isinstance(table, Table)
    assert table.title == "Test Table"
    assert table.row_count == 2

    # Verify that the table object was constructed successfully and passed to print
    # The exact row content inspection is limited by Rich's public API on the Table object,
    # but successfully reaching this point confirms no exceptions during row addition.

def test_display_header(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_header("Test Header")
    mock_console.print.assert_called_once()
    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Panel)
    # Accessing the renderable inside Panel might be tricky, but we can check implementation details if needed
    # or just assert it was called.

def test_display_section(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_section("Test Section")
    mock_console.print.assert_called_once()
    assert "Test Section" in mock_console.print.call_args[0][0]

def test_display_status(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_status("Status Update")
    mock_console.print.assert_called_once()
    assert "Status Update" in mock_console.print.call_args[0][0]

def test_display_error(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_error("Something went wrong")
    mock_console.print.assert_called_once()
    assert "Something went wrong" in mock_console.print.call_args[0][0]

def test_display_success(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_success("Operation successful")
    mock_console.print.assert_called_once()
    assert "Operation successful" in mock_console.print.call_args[0][0]

def test_display_info(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_info("Information")
    mock_console.print.assert_called_once()
    assert "Information" in mock_console.print.call_args[0][0]

def test_display_message(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_message("Just a message")
    mock_console.print.assert_called_once_with("Just a message")

def test_loading(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    # Configure status to return a context manager
    mock_console.status.return_value.__enter__ = MagicMock()
    mock_console.status.return_value.__exit__ = MagicMock()

    with ui.loading("Loading..."):
        pass
    mock_console.status.assert_called_once_with("Loading...", spinner="dots")

def test_display_stream(ui: RichConsoleUI, mock_console: MagicMock, mocker: Any) -> None:
    async def mock_generator() -> AsyncGenerator[str, None]:
        yield "Hello"
        yield " "
        yield "World"

    # Mock Live context manager
    mock_live = mocker.patch("src.core.ui.Live")
    mock_live_instance = mock_live.return_value
    mock_live_instance.__enter__.return_value = mock_live_instance

    # Since display_stream is async, we run it with asyncio.run
    asyncio.run(ui.display_stream(mock_generator()))

    # Verify Live was initialized with console
    mock_live.assert_called_once()
    assert mock_live.call_args[1]['console'] == mock_console

    # Verify update was called
    assert mock_live_instance.update.called

    # Verify console.print() was called at the end for newline
    mock_console.print.assert_called_with()
