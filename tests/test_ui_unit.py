import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from src.core.ui import RichConsoleUI

def test_display_header():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_header("Test Header")

    assert mock_console.print.called
    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Panel)

def test_display_section():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_section("Test Section")

    mock_console.print.assert_called_with("\n[bold cyan]--- Test Section ---[/bold cyan]")

def test_display_status():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_status("Status Update")

    mock_console.print.assert_called_with("[yellow]Status Update[/yellow]")

def test_display_table_empty():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)
    df = pd.DataFrame()

    ui.display_table(df)

    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

def test_display_table_with_data():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)
    df = pd.DataFrame({
        'A': [1, 2],
        'B': ['x', 'y']
    })

    ui.display_table(df, title="Test Table")

    assert mock_console.print.called
    args, _ = mock_console.print.call_args
    assert isinstance(args[0], Table)
    table = args[0]
    assert table.title == "Test Table"
    assert len(table.columns) == 2
    assert table.columns[0].header == "A"
    assert table.columns[1].header == "B"

def test_display_error():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_error("Something went wrong")

    mock_console.print.assert_called_with("[bold red]Error:[/bold red] Something went wrong")

def test_display_success():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_success("Great success")

    mock_console.print.assert_called_with("[bold green]✔ Great success[/bold green]")

def test_display_info():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_info("Just info")

    mock_console.print.assert_called_with("[blue]ℹ Just info[/blue]")

def test_display_message():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    ui.display_message("Hello World")

    mock_console.print.assert_called_with("Hello World")

def test_loading():
    mock_console = Mock(spec=Console)
    # Configure status to return a context manager mock
    mock_status = MagicMock()
    mock_console.status.return_value = mock_status
    mock_status.__enter__.return_value = mock_status

    ui = RichConsoleUI(console=mock_console)

    with ui.loading("Loading..."):
        pass

    mock_console.status.assert_called_with("Loading...", spinner="dots")

@pytest.mark.asyncio
async def test_display_stream():
    mock_console = Mock(spec=Console)
    ui = RichConsoleUI(console=mock_console)

    async def mock_generator():
        yield "Hello "
        yield "World"

    # Patch Live to avoid actual rendering and verify interaction
    with patch('src.core.ui.Live') as MockLive:
        mock_live_instance = MockLive.return_value
        # Context manager support
        mock_live_instance.__enter__.return_value = mock_live_instance

        await ui.display_stream(mock_generator())

        # Verify Live was initialized with ui.console
        assert MockLive.called
        _, kwargs = MockLive.call_args
        assert kwargs['console'] == mock_console

        # Verify update was called twice
        assert mock_live_instance.update.call_count == 2
