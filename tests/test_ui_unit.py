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
    mock_console.print.assert_called_with(
        "[italic dim]No data available.[/italic dim]")


def test_display_table_columns(ui: RichConsoleUI, mock_console: Mock) -> None:
    data = pd.DataFrame({
        "A": ["string"],
        "B": [1],
        "Views": [100]
    })
    ui.display_table(data)

    # Check if a Table was printed
    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Table)
    table = args[0]

    # Check columns
    # Column A: String -> justify="left", style="cyan"
    assert table.columns[0].header == "A"
    assert table.columns[0].justify == "left"
    assert table.columns[0].style == "cyan"

    # Column B: Numeric -> justify="right", style="green"
    assert table.columns[1].header == "B"
    assert table.columns[1].justify == "right"
    assert table.columns[1].style == "green"

    # Column Views: Name matches -> justify="right", style="green"
    assert table.columns[2].header == "Views"
    assert table.columns[2].justify == "right"
    assert table.columns[2].style == "green"


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
    assert col2_cells == ["10", "20"]  # converted to string


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
    mock_console.print.assert_called_with(
        "\n[bold cyan]--- Section ---[/bold cyan]")


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
