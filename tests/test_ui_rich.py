import pytest
import pandas as pd
import asyncio
from unittest.mock import Mock, patch
from src.core.ui import RichConsoleUI
from rich.table import Table
from rich.panel import Panel
from typing import AsyncGenerator, Any, List

@pytest.fixture
def mock_console() -> Mock:
    return Mock()

@pytest.fixture
def rich_ui(mock_console: Mock) -> RichConsoleUI:
    ui = RichConsoleUI()
    ui.console = mock_console
    return ui

def test_display_table_empty(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    df = pd.DataFrame()
    rich_ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Title", ["Video 1", "Video 2"], "left", "cyan"),
    ("Views", [100, 200], "right", "green"),
    ("Retention", [0.5, 0.6], "right", "green"),
    ("Retention (%)", ["50%", "60%"], "right", "green"),
    ("Other Metric", [1, 2], "right", "green"),
])
def test_display_table_formatting(
    rich_ui: RichConsoleUI,
    mock_console: Mock,
    col_name: str,
    col_data: List[Any],
    expected_justify: str,
    expected_style: str
) -> None:
    df = pd.DataFrame({col_name: col_data})
    rich_ui.display_table(df)

    assert mock_console.print.called
    args, _ = mock_console.print.call_args
    table = args[0]

    assert isinstance(table, Table)
    column = table.columns[0]
    assert column.header == col_name
    assert column.justify == expected_justify
    assert column.style == expected_style
    assert table.row_count == 2

def test_display_table_mixed(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    df = pd.DataFrame({
        "Title": ["A", "B"],
        "Views": [10, 20]
    })
    rich_ui.display_table(df)

    args, _ = mock_console.print.call_args
    table = args[0]

    assert len(table.columns) == 2
    assert table.columns[0].header == "Title"
    assert table.columns[0].style == "cyan"
    assert table.columns[1].header == "Views"
    assert table.columns[1].style == "green"

def test_display_header(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_header("Test Header")
    args, _ = mock_console.print.call_args
    panel = args[0]
    assert isinstance(panel, Panel)
    assert "Test Header" in str(panel.renderable)

def test_display_section(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_section("Test Section")
    mock_console.print.assert_called_with("\n[bold cyan]--- Test Section ---[/bold cyan]")

def test_display_status(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_status("Test Status")
    mock_console.print.assert_called_with("[yellow]Test Status[/yellow]")

def test_display_error(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_error("Test Error")
    mock_console.print.assert_called_with("[bold red]Error:[/bold red] Test Error")

def test_display_success(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_success("Great Job")
    mock_console.print.assert_called_with("[bold green]✔ Great Job[/bold green]")

def test_display_info(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_info("FYI")
    mock_console.print.assert_called_with("[blue]ℹ FYI[/blue]")

def test_display_message(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.display_message("Hello")
    mock_console.print.assert_called_with("Hello")

def test_loading(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    rich_ui.loading("Loading...")
    mock_console.status.assert_called_with("Loading...", spinner="dots")

def test_display_stream(rich_ui: RichConsoleUI, mock_console: Mock) -> None:
    async def mock_gen() -> AsyncGenerator[str, None]:
        yield "Part 1"
        yield "Part 2"

    with patch("src.core.ui.Live") as MockLive:
        # Setup the context manager return value
        live_instance = MockLive.return_value
        live_instance.__enter__.return_value = live_instance

        asyncio.run(rich_ui.display_stream(mock_gen()))

        assert MockLive.called
        assert live_instance.update.called
        assert live_instance.update.call_count >= 2
