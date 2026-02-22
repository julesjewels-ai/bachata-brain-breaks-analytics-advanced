import pytest
from unittest.mock import Mock
from pytest_mock import MockerFixture
import pandas as pd
import asyncio
from typing import List, Any

from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console_class(mocker: MockerFixture) -> Mock:
    """Mocks the Console class imported in src.core.ui."""
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table_class(mocker: MockerFixture) -> Mock:
    """Mocks the Table class imported in src.core.ui."""
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def mock_live_class(mocker: MockerFixture) -> Mock:
    """Mocks the Live class imported in src.core.ui."""
    return mocker.patch("src.core.ui.Live")

@pytest.fixture
def ui(mock_console_class: Mock) -> RichConsoleUI:
    """Returns a RichConsoleUI instance with a mocked console."""
    return RichConsoleUI()

def test_init(ui: RichConsoleUI, mock_console_class: Mock) -> None:
    """Test initialization creates a Console instance."""
    mock_console_class.assert_called_once()
    assert ui.console == mock_console_class.return_value, "Console instance not assigned correctly"

def test_display_header(ui: RichConsoleUI) -> None:
    """Test display_header prints a Panel."""
    ui.display_header("Test Header")
    # We can't easily assert the exact Panel object equality, but we can check call args
    ui.console.print.assert_called_once()
    args, _ = ui.console.print.call_args
    # First arg should be a Panel
    from rich.panel import Panel
    assert isinstance(args[0], Panel), "First argument should be a rich Panel"
    assert args[0].renderable.plain == "Test Header", "Panel content mismatch"

def test_display_section(ui: RichConsoleUI) -> None:
    """Test display_section prints formatted text."""
    ui.display_section("Test Section")
    ui.console.print.assert_called_with("\n[bold cyan]--- Test Section ---[/bold cyan]")

def test_display_status(ui: RichConsoleUI) -> None:
    """Test display_status prints yellow text."""
    ui.display_status("Status Update")
    ui.console.print.assert_called_with("[yellow]Status Update[/yellow]")

def test_display_error(ui: RichConsoleUI) -> None:
    """Test display_error prints red error text."""
    ui.display_error("Something went wrong")
    ui.console.print.assert_called_with("[bold red]Error:[/bold red] Something went wrong")

def test_display_success(ui: RichConsoleUI) -> None:
    """Test display_success prints green success text."""
    ui.display_success("Operation complete")
    ui.console.print.assert_called_with("[bold green]✔ Operation complete[/bold green]")

def test_display_info(ui: RichConsoleUI) -> None:
    """Test display_info prints blue info text."""
    ui.display_info("Information")
    ui.console.print.assert_called_with("[blue]ℹ Information[/blue]")

def test_display_message(ui: RichConsoleUI) -> None:
    """Test display_message prints raw text."""
    ui.display_message("Hello World")
    ui.console.print.assert_called_with("Hello World")

def test_loading(ui: RichConsoleUI) -> None:
    """Test loading returns a status context manager."""
    with ui.loading("Loading..."):
        pass
    ui.console.status.assert_called_with("Loading...", spinner="dots")

def test_display_table_empty(ui: RichConsoleUI) -> None:
    """Test display_table with empty DataFrame."""
    df = pd.DataFrame()
    ui.display_table(df)
    ui.console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Title", ["Video A"], "left", "cyan"),
    ("Views", [100], "right", "green"),
    ("Retention", [0.5], "right", "green"),
    ("Retention (%)", [50.0], "right", "green"),
    ("Other Numeric", [123], "right", "green"), # Numeric dtype
    ("Other String", ["Text"], "left", "cyan"),
])
def test_display_table_columns_styling(
    ui: RichConsoleUI,
    mock_table_class: Mock,
    col_name: str,
    col_data: List[Any],
    expected_justify: str,
    expected_style: str
) -> None:
    """Test column justification and styling logic."""
    df = pd.DataFrame({col_name: col_data})
    mock_table_instance = mock_table_class.return_value

    ui.display_table(df, title="Test Table")

    # verify table creation
    mock_table_class.assert_called_once()
    assert mock_table_class.call_args[1]['title'] == "Test Table", "Table title mismatch"

    # verify add_column call
    mock_table_instance.add_column.assert_called_with(
        str(col_name), justify=expected_justify, style=expected_style
    )

def test_display_table_rows(ui: RichConsoleUI, mock_table_class: Mock) -> None:
    """Test that rows are added correctly as strings."""
    df = pd.DataFrame({
        "Title": ["Video 1", "Video 2"],
        "Views": [100, 200],
        "Score": [1.5, None] # Mixed types/NaN
    })
    mock_table_instance = mock_table_class.return_value

    ui.display_table(df)

    # Check add_row calls
    assert mock_table_instance.add_row.call_count == 2, "Should add 2 rows"

    # First row
    call_args1 = mock_table_instance.add_row.call_args_list[0]
    # args are unpacked (*rendered_row), so we check args tuple
    assert call_args1[0] == ("Video 1", "100", "1.5"), "First row content mismatch"

    # Second row
    call_args2 = mock_table_instance.add_row.call_args_list[1]
    assert call_args2[0] == ("Video 2", "200", "nan"), "Second row content mismatch (NaN check)"

    ui.console.print.assert_called_with(mock_table_instance)

def test_display_stream(ui: RichConsoleUI, mock_live_class: Mock) -> None:
    """Test display_stream updates Live display with accumulated text."""
    async def run_test() -> None:
        async def mock_generator():
            yield "Hello "
            yield "World"

        mock_live_instance = mock_live_class.return_value
        # Use context manager mock
        mock_live_instance.__enter__.return_value = mock_live_instance

        # Capture state of Text object when update is called
        captured_states = []
        def capture_state(text_obj):
            captured_states.append(text_obj.plain)

        mock_live_instance.update.side_effect = capture_state

        await ui.display_stream(mock_generator())

        mock_live_class.assert_called_once()
        # Check that update was called twice
        assert mock_live_instance.update.call_count == 2, "Live.update should be called twice"

        # Verify captured states
        assert captured_states[0] == "Hello ", "First update mismatch"
        assert captured_states[1] == "Hello World", "Second update mismatch"

        ui.console.print.assert_called_with() # Final newline

    asyncio.run(run_test())
