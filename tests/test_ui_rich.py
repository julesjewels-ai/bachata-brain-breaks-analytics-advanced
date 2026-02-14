import pytest
from unittest.mock import MagicMock
import pandas as pd
from typing import Any, AsyncGenerator
from rich.panel import Panel
from rich import box

from src.core.ui import RichConsoleUI

# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------

@pytest.fixture
def mock_console(mocker):
    """Mocks the Console class where it is instantiated in RichConsoleUI."""
    # Since RichConsoleUI instantiates Console() in __init__, we patch the class.
    # Note: We must patch 'src.core.ui.Console' because that's where the import is used.
    mock_console_cls = mocker.patch("src.core.ui.Console")
    mock_instance = mock_console_cls.return_value
    return mock_instance

@pytest.fixture
def ui(mock_console):
    """Returns an instance of RichConsoleUI with a mocked console."""
    return RichConsoleUI()

# -----------------------------------------------------------------------------
# Test: display_header
# -----------------------------------------------------------------------------

def test_display_header(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Test Header"
    ui.display_header(text)

    # Verify print was called
    assert mock_console.print.called

    # Verify arguments: It should be a Panel
    args, _ = mock_console.print.call_args
    assert len(args) == 1
    assert isinstance(args[0], Panel)
    # Ideally we'd inspect the Panel content, but that might be implementation detail heavy.
    # Just checking it's a Panel is a good start.

# -----------------------------------------------------------------------------
# Test: display_section
# -----------------------------------------------------------------------------

def test_display_section(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Section Title"
    ui.display_section(text)

    # Check that print was called with the formatted string
    mock_console.print.assert_called_with(f"\n[bold cyan]--- {text} ---[/bold cyan]")

# -----------------------------------------------------------------------------
# Test: display_status
# -----------------------------------------------------------------------------

def test_display_status(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Status update"
    ui.display_status(text)
    mock_console.print.assert_called_with(f"[yellow]{text}[/yellow]")

# -----------------------------------------------------------------------------
# Test: display_table
# -----------------------------------------------------------------------------

def test_display_table_empty(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    """Test that an empty DataFrame triggers the 'No data available' message."""
    df = pd.DataFrame()
    ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("data_dict, expected_columns, expected_rows_str", [
    # Case 1: Simple numeric data (should be right-aligned, green)
    (
        {"A": [1, 2], "B": [3, 4]},
        [("A", "right", "green"), ("B", "right", "green")],
        [["1", "3"], ["2", "4"]]
    ),
    # Case 2: String data (should be left-aligned, cyan)
    (
        {"Name": ["Alice", "Bob"], "Role": ["User", "Admin"]},
        [("Name", "left", "cyan"), ("Role", "left", "cyan")],
        [["Alice", "User"], ["Bob", "Admin"]]
    ),
    # Case 3: Mixed (Numeric + String)
    (
        {"Views": [100, 200], "Category": ["A", "B"]},
        [("Views", "right", "green"), ("Category", "left", "cyan")],
        [["100", "A"], ["200", "B"]]
    ),
     # Case 4: Specific column name 'Retention' (should be right-aligned, green even if object/float)
    (
        {"Retention": [0.5, 0.6]},
        [("Retention", "right", "green")],
        [["0.5"], ["0.6"]]
    ),
    # Case 5: 'Retention (%)' (should be right-aligned, green)
    (
        {"Retention (%)": ["50%", "60%"]}, # Even if string, name triggers style?
        [("Retention (%)", "right", "green")],
        [["50%"], ["60%"]]
    ),
     # Case 6: 'Views' (should be right-aligned, green)
    (
        {"Views": ["100k", "200k"]}, # Even if string? Let's check logic.
        [("Views", "right", "green")],
        [["100k"], ["200k"]]
    ),
    # Case 7: Mixed types in a row (converted to string)
    (
        {"Mixed": [1, "two", 3.0]},
        [("Mixed", "left", "cyan")], # Mixed type column in pandas is usually object, so not numeric.
        [["1"], ["two"], ["3.0"]]
    )
])
def test_display_table_content(
    ui: RichConsoleUI,
    mock_console: MagicMock,
    mocker: Any,
    data_dict: dict,
    expected_columns: list,
    expected_rows_str: list
) -> None:
    df = pd.DataFrame(data_dict)

    # Mock Table class to verify instantiation and methods
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df, title="Test Table")

    # Verify Table instantiation
    mock_table_cls.assert_called_with(title="Test Table", box=box.ROUNDED)

    # Verify add_column calls
    # Note: df.columns order is preserved from dict if python 3.7+ (assumed)
    assert mock_table_instance.add_column.call_count == len(expected_columns)
    for (col_name, justify, style) in expected_columns:
        mock_table_instance.add_column.assert_any_call(str(col_name), justify=justify, style=style)

    # Verify add_row calls
    assert mock_table_instance.add_row.call_count == len(expected_rows_str)
    for row_values in expected_rows_str:
        mock_table_instance.add_row.assert_any_call(*row_values)

    # Verify console.print called with the table instance
    mock_console.print.assert_called_with(mock_table_instance)

def test_display_table_with_none(ui: RichConsoleUI, mock_console: MagicMock, mocker: Any) -> None:
    """Test handling of None/NaN values."""
    # Explicitly use object dtype to preserve None
    df = pd.DataFrame({"Data": [None, "Value"]}, dtype=object)

    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df)

    # Expect None to be converted to 'None' string or 'nan' depending on pandas behavior
    # pandas usually converts None to NaN for numeric, but object keeps None.
    # However, str(None) is 'None'. str(np.nan) is 'nan'.
    # Let's see what happens.

    # If we use object dtype, None is preserved.
    # row 1: [None] -> str(None) -> 'None'
    # row 2: ["Value"] -> "Value"

    # But wait, pandas might convert to float nan if column was mixed? No, we forced object.

    # Let's just capture what add_row was called with.
    calls = mock_table_instance.add_row.call_args_list
    assert len(calls) == 2

    # Check the first row call arguments
    args1, _ = calls[0]
    # We expect "None" or "nan". Since we used None in python list and object dtype.
    # Actually, pandas might behave differently. Let's make the test flexible or verify behavior.
    # Just asserting it calls add_row is good, but checking content is better.
    # Let's assume str(None) -> 'None'.
    # If pandas converts to NaN (float), str(NaN) -> 'nan'.

    # To be safe against pandas version changes, we can accept both or check type.
    val = args1[0]
    assert val in ["None", "nan"]

# -----------------------------------------------------------------------------
# Test: display_error
# -----------------------------------------------------------------------------

def test_display_error(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    error_msg = "Something went wrong"
    ui.display_error(error_msg)
    mock_console.print.assert_called_with(f"[bold red]Error:[/bold red] {error_msg}")

    # Test with Exception object
    exc = ValueError("Invalid value")
    ui.display_error(exc)
    mock_console.print.assert_called_with(f"[bold red]Error:[/bold red] {exc}")

# -----------------------------------------------------------------------------
# Test: display_success, display_info, display_message
# -----------------------------------------------------------------------------

def test_display_success(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Success!"
    ui.display_success(text)
    mock_console.print.assert_called_with(f"[bold green]✔ {text}[/bold green]")

def test_display_info(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Info..."
    ui.display_info(text)
    mock_console.print.assert_called_with(f"[blue]ℹ {text}[/blue]")

def test_display_message(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Just a message"
    ui.display_message(text)
    mock_console.print.assert_called_with(text)

# -----------------------------------------------------------------------------
# Test: loading
# -----------------------------------------------------------------------------

def test_loading(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    text = "Loading..."
    # loading returns a context manager (console.status)
    ctx = ui.loading(text)

    mock_console.status.assert_called_with(text, spinner="dots")
    assert ctx == mock_console.status.return_value

# -----------------------------------------------------------------------------
# Test: display_stream (Async)
# -----------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_display_stream(ui: RichConsoleUI, mock_console: MagicMock, mocker: Any) -> None:
    async def mock_generator() -> AsyncGenerator[str, None]:
        yield "Chunk 1"
        yield "Chunk 2"

    # Mock Live context manager
    mock_live_cls = mocker.patch("src.core.ui.Live")
    mock_live_instance = mock_live_cls.return_value
    mock_live_instance.__enter__.return_value = mock_live_instance
    mock_live_instance.__exit__.return_value = None

    await ui.display_stream(mock_generator())

    # Verify Live was initialized
    mock_live_cls.assert_called()

    # Verify update was called for each chunk
    # Initial Text is created empty.
    # Chunk 1: appended. update called.
    # Chunk 2: appended. update called.
    assert mock_live_instance.update.call_count == 2

    # Verify final newline
    # The method calls self.console.print() at the end
    mock_console.print.assert_called()
