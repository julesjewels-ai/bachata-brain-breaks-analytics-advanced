"""
Tests for RichConsoleUI.
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, call
from src.core.ui import RichConsoleUI
from rich.panel import Panel

@pytest.fixture
def mock_console(mocker):
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table(mocker):
    return mocker.patch("src.core.ui.Table")

def test_display_header(mock_console):
    ui = RichConsoleUI()
    ui.display_header("Test Header")

    # Verify print was called with a Panel
    assert ui.console.print.called
    args, _ = ui.console.print.call_args
    assert isinstance(args[0], Panel)
    assert args[0].renderable.plain == "Test Header"

def test_display_section(mock_console):
    ui = RichConsoleUI()
    ui.display_section("Test Section")
    ui.console.print.assert_called_with("\n[bold cyan]--- Test Section ---[/bold cyan]")

def test_display_status(mock_console):
    ui = RichConsoleUI()
    ui.display_status("Test Status")
    ui.console.print.assert_called_with("[yellow]Test Status[/yellow]")

def test_display_error(mock_console):
    ui = RichConsoleUI()
    ui.display_error("Test Error")
    ui.console.print.assert_called_with("[bold red]Error:[/bold red] Test Error")

def test_display_success(mock_console):
    ui = RichConsoleUI()
    ui.display_success("Test Success")
    ui.console.print.assert_called_with("[bold green]✔ Test Success[/bold green]")

def test_display_info(mock_console):
    ui = RichConsoleUI()
    ui.display_info("Test Info")
    ui.console.print.assert_called_with("[blue]ℹ Test Info[/blue]")

def test_display_message(mock_console):
    ui = RichConsoleUI()
    ui.display_message("Test Message")
    ui.console.print.assert_called_with("Test Message")

def test_display_table_empty(mock_console, mock_table):
    ui = RichConsoleUI()
    df = pd.DataFrame()
    ui.display_table(df)
    ui.console.print.assert_called_with("[italic dim]No data available.[/italic dim]")
    mock_table.assert_not_called()

def test_display_table_numeric_formatting(mock_console, mock_table):
    ui = RichConsoleUI()
    mock_table_instance = mock_table.return_value

    df = pd.DataFrame({'Views': [100], 'Retention': [50.5]})
    ui.display_table(df)

    mock_table.assert_called()
    mock_table_instance.add_column.assert_has_calls([
        call('Views', justify='right', style='green'),
        call('Retention', justify='right', style='green')
    ])

def test_display_table_integer_preservation(mock_console, mock_table):
    """
    Test that integers are preserved and not coerced to floats
    when using itertuples instead of iterrows.
    """
    ui = RichConsoleUI()
    mock_table_instance = mock_table.return_value

    # Create a DataFrame where row-wise iteration might convert int to float
    # if iterrows is used (because the row becomes a Series of floats)
    df = pd.DataFrame({
        'IntCol': [1, 2],
        'FloatCol': [1.5, 2.5]
    })

    ui.display_table(df)

    # Check what was passed to add_row
    # We expect "1" not "1.0" for IntCol
    mock_table_instance.add_row.assert_has_calls([
        call("1", "1.5"),
        call("2", "2.5")
    ])

def test_display_table_none_handling(mock_console, mock_table):
    """
    Test that None values are converted to 'nan'.
    """
    ui = RichConsoleUI()
    mock_table_instance = mock_table.return_value

    # Use object dtype to allow None
    df = pd.DataFrame({'Col': [None, 1]}, dtype=object)

    ui.display_table(df)

    mock_table_instance.add_row.assert_has_calls([
        call("nan"),
        call("1")
    ])

@pytest.mark.asyncio
async def test_display_stream(mock_console, mocker):
    # Mock Live context manager
    mock_live = mocker.patch("src.core.ui.Live")
    mock_live_instance = MagicMock()
    mock_live.return_value.__enter__.return_value = mock_live_instance

    ui = RichConsoleUI()

    async def generator():
        yield "chunk1"
        yield "chunk2"

    await ui.display_stream(generator())

    assert mock_live.called
    assert mock_live_instance.update.call_count == 2
