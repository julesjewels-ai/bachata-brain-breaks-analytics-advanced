"""
Unit tests for the RichConsoleUI class in src.core.ui.
These tests verify the display logic without requiring actual console output.
"""
import pytest
from unittest.mock import Mock, call, MagicMock
import pandas as pd
from typing import AsyncGenerator
import asyncio

from src.core.ui import RichConsoleUI

from pytest_mock import MockerFixture

@pytest.fixture
def mock_console(mocker: MockerFixture) -> Mock:
    """Fixture to mock the rich Console."""
    return mocker.patch("src.core.ui.Console", autospec=True)

@pytest.fixture
def ui(mock_console: Mock) -> RichConsoleUI:
    """Fixture to create a RichConsoleUI instance with a mocked console."""
    return RichConsoleUI()

def test_display_table_empty(ui: RichConsoleUI, mock_console: Mock) -> None:
    """Test that display_table handles empty DataFrames correctly."""
    # Arrange
    df = pd.DataFrame()

    # Act
    ui.display_table(df)

    # Assert
    # Access the instance of the mocked Console class
    console_instance = ui.console # type: ignore
    console_instance.print.assert_called_with("[italic dim]No data available.[/italic dim]")

def test_display_table_structure(ui: RichConsoleUI, mocker: MockerFixture) -> None:
    """Test that display_table creates a Table with correct title and box style."""
    # Arrange
    df = pd.DataFrame({"col1": [1, 2], "col2": ["a", "b"]})
    mock_table_cls = mocker.patch("src.core.ui.Table", autospec=True)
    mock_box = mocker.patch("src.core.ui.box", autospec=True)

    # Act
    ui.display_table(df, title="Test Table")

    # Assert
    mock_table_cls.assert_called_once_with(title="Test Table", box=mock_box.ROUNDED)

    # Verify columns were added
    table_instance = mock_table_cls.return_value
    assert table_instance.add_column.call_count == 2

    # Verify rows were added
    assert table_instance.add_row.call_count == 2

    # Verify table was printed
    ui.console.print.assert_called_with(table_instance) # type: ignore

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Numeric", [1, 2, 3], "right", "green"),
    ("String", ["a", "b", "c"], "left", "cyan"),
    ("Views", ["100", "200"], "right", "green"), # Special column name
    ("Retention", ["50%", "60%"], "right", "green"), # Special column name
    ("Retention (%)", [0.5, 0.6], "right", "green"), # Special column name
    ("Mixed", [1, "two"], "left", "cyan"), # Mixed types usually default to object/string logic unless specific check passes
])
def test_display_table_columns_styling(
    ui: RichConsoleUI,
    mocker: MockerFixture,
    col_name: str,
    col_data: list,
    expected_justify: str,
    expected_style: str
) -> None:
    """Test column styling logic based on data type and column name."""
    # Arrange
    df = pd.DataFrame({col_name: col_data})
    mock_table_cls = mocker.patch("src.core.ui.Table", autospec=True)
    table_instance = mock_table_cls.return_value

    # Act
    ui.display_table(df)

    # Assert
    # verify add_column was called with expected style
    table_instance.add_column.assert_called_with(
        str(col_name), justify=expected_justify, style=expected_style
    )

def test_display_table_rows(ui: RichConsoleUI, mocker: MockerFixture) -> None:
    """Test that rows are added with string conversion."""
    # Arrange
    df = pd.DataFrame({
        "A": [1, 2],
        "B": ["x", "y"]
    })
    mock_table_cls = mocker.patch("src.core.ui.Table", autospec=True)
    table_instance = mock_table_cls.return_value

    # Act
    ui.display_table(df)

    # Assert
    # Check that add_row was called with stringified values
    expected_calls = [
        call("1", "x"),
        call("2", "y")
    ]
    table_instance.add_row.assert_has_calls(expected_calls)

@pytest.mark.asyncio
async def test_display_stream(ui: RichConsoleUI, mocker: MockerFixture) -> None:
    """Test the async display_stream method."""
    # Arrange
    mock_live_cls = mocker.patch("src.core.ui.Live")
    mock_live_instance = mock_live_cls.return_value
    # Use context manager protocol
    mock_live_instance.__enter__.return_value = mock_live_instance
    mock_live_instance.__exit__.return_value = None

    async def mock_generator() -> AsyncGenerator[str, None]:
        yield "Hello"
        yield " "
        yield "World"

    # Act
    await ui.display_stream(mock_generator())

    # Assert
    assert mock_live_cls.call_count == 1
    # Check that update was called for each chunk
    # Since Text() is mutable and appended to, checking exact calls on update might be tricky
    # without deeper introspection of the Text object state at call time.
    # But we can verify it was called 3 times.
    assert mock_live_instance.update.call_count == 3

    # Verify console.print() was called at the end (for newline)
    ui.console.print.assert_called() # type: ignore

def test_display_simple_methods(ui: RichConsoleUI, mocker: MockerFixture) -> None:
    """Test simple display methods that just print text."""
    # Test display_header
    mock_panel = mocker.patch("src.core.ui.Panel")
    mock_text = mocker.patch("src.core.ui.Text")

    ui.display_header("Header")
    ui.console.print.assert_called() # type: ignore
    mock_panel.assert_called()
    mock_text.assert_called()

    # Test display_section
    ui.display_section("Section")
    ui.console.print.assert_called_with("\n[bold cyan]--- Section ---[/bold cyan]") # type: ignore

    # Test display_status
    ui.display_status("Status")
    ui.console.print.assert_called_with("[yellow]Status[/yellow]") # type: ignore

    # Test display_error
    ui.display_error("Error")
    ui.console.print.assert_called_with("[bold red]Error:[/bold red] Error") # type: ignore

    # Test display_success
    ui.display_success("Success")
    ui.console.print.assert_called_with("[bold green]✔ Success[/bold green]") # type: ignore

    # Test display_info
    ui.display_info("Info")
    ui.console.print.assert_called_with("[blue]ℹ Info[/blue]") # type: ignore

    # Test display_message
    ui.display_message("Message")
    ui.console.print.assert_called_with("Message") # type: ignore

def test_loading(ui: RichConsoleUI) -> None:
    """Test loading context manager."""
    ctx = ui.loading("Loading...")
    ui.console.status.assert_called_with("Loading...", spinner="dots")
