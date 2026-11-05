import pytest
from unittest.mock import Mock, call, MagicMock, patch
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from src.core.ui import RichConsoleUI
from typing import AsyncGenerator

@pytest.fixture
def mock_console() -> Mock:
    return Mock(spec=Console)

@pytest.fixture
def ui(mock_console: Mock) -> RichConsoleUI:
    return RichConsoleUI(console=mock_console)

def test_display_table_empty(ui: RichConsoleUI, mock_console: Mock) -> None:
    data = pd.DataFrame()
    ui.display_table(data)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name,col_data,expected_justify,expected_style", [
    ("A", ["string"], "left", "cyan"),
    ("B", [1], "right", "green"),
    ("Views", [100], "right", "green"),
    ("Retention", [50], "right", "green"),
    ("Retention (%)", [50.5], "right", "green"),
    ("Title", ["Hello"], "left", "cyan"),
])
def test_display_table_columns(
    ui: RichConsoleUI,
    mock_console: Mock,
    col_name: str,
    col_data: list,
    expected_justify: str,
    expected_style: str
) -> None:
    data = pd.DataFrame({col_name: col_data})
    ui.display_table(data)

    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Table), f"Failed on column: {col_name}, expected a Table to be printed."
    table = args[0]

    assert table.columns[0].header == col_name, f"Failed on column header for: {col_name}"
    assert table.columns[0].justify == expected_justify, f"Failed on column justify for: {col_name}"
    assert table.columns[0].style == expected_style, f"Failed on column style for: {col_name}"

def test_display_table_rows(ui: RichConsoleUI, mock_console: Mock) -> None:
    data = pd.DataFrame({
        "Col1": ["Val1", "Val2"],
        "Col2": [10, 20]
    })
    ui.display_table(data)

    args, _ = mock_console.print.call_args
    table = args[0]

    # Check rows by inspecting column cells
    # Convert generator to list to check content
    col1_cells = list(table.columns[0].cells)
    assert col1_cells == ["Val1", "Val2"]

    col2_cells = list(table.columns[1].cells)
    assert col2_cells == ["10", "20"] # converted to string

@pytest.mark.asyncio
async def test_display_stream(ui: RichConsoleUI, mock_console: Mock) -> None:
    async def sample_generator() -> AsyncGenerator[str, None]:
        yield "Hello"
        yield " "
        yield "World"

    # We patch 'src.core.ui.Live' because that's where the class is looked up
    with patch("src.core.ui.Live") as mock_live_cls:
        # The context manager returns the instance
        mock_live_instance = mock_live_cls.return_value
        mock_live_instance.__enter__.return_value = mock_live_instance

        await ui.display_stream(sample_generator())

        # Verify Live was initialized correctly
        # call_args[0] are positional args: (text_buffer,)
        # call_args[1] are kwargs: {console=..., refresh_per_second=...}
        assert mock_live_cls.called
        call_args = mock_live_cls.call_args
        assert isinstance(call_args[0][0], Text)
        assert call_args[1]["console"] == mock_console

        # Verify update was called 3 times (once per chunk)
        assert mock_live_instance.update.call_count == 3

        # Verify final newline
        mock_console.print.assert_called()

def test_loading(ui: RichConsoleUI, mock_console: Mock) -> None:
    context = ui.loading("Loading...")
    mock_console.status.assert_called_with("Loading...", spinner="dots")
    assert context == mock_console.status.return_value

def test_display_header(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_header("Header")
    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Panel)

def test_display_section(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_section("Section")
    mock_console.print.assert_called_with("\n[bold cyan]--- Section ---[/bold cyan]")

def test_display_status(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_status("Status")
    mock_console.print.assert_called_with("[yellow]Status[/yellow]")

def test_display_error(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_error("Error")
    mock_console.print.assert_called_with("[bold red]Error:[/bold red] Error")

def test_display_success(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_success("Success")
    mock_console.print.assert_called_with("[bold green]✔ Success[/bold green]")

def test_display_info(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_info("Info")
    mock_console.print.assert_called_with("[blue]ℹ Info[/blue]")

def test_display_message(ui: RichConsoleUI, mock_console: Mock) -> None:
    ui.display_message("Message")
    mock_console.print.assert_called_with("Message")
