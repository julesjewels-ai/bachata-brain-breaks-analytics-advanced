import pytest
import pandas as pd
import asyncio
from typing import List, Tuple, Any, Optional
from rich.panel import Panel
from rich.text import Text
from rich import box
from src.core.ui import RichConsoleUI
from pytest_mock import MockerFixture
from unittest.mock import MagicMock

@pytest.fixture
def mock_console(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def ui(mock_console: MagicMock, mock_table: MagicMock) -> RichConsoleUI:
    return RichConsoleUI()

def test_display_header(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_header("Test Header")
    mock_console.return_value.print.assert_called_once()
    args, _ = mock_console.return_value.print.call_args
    assert isinstance(args[0], Panel)

def test_display_section(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_section("Test Section")
    mock_console.return_value.print.assert_called_once_with("\n[bold cyan]--- Test Section ---[/bold cyan]")

def test_display_status(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_status("Test Status")
    mock_console.return_value.print.assert_called_once_with("[yellow]Test Status[/yellow]")

def test_display_error(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_error("Test Error")
    mock_console.return_value.print.assert_called_once_with("[bold red]Error:[/bold red] Test Error")

def test_display_success(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_success("Test Success")
    mock_console.return_value.print.assert_called_once_with("[bold green]✔ Test Success[/bold green]")

def test_display_info(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_info("Test Info")
    mock_console.return_value.print.assert_called_once_with("[blue]ℹ Test Info[/blue]")

def test_display_message(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.display_message("Test Message")
    mock_console.return_value.print.assert_called_once_with("Test Message")

def test_loading(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    ui.loading("Loading...")
    mock_console.return_value.status.assert_called_once_with("Loading...", spinner="dots")

def test_display_stream(ui: RichConsoleUI, mock_console: MagicMock, mocker: MockerFixture) -> None:
    mock_live = mocker.patch("src.core.ui.Live")
    mock_live_instance = mock_live.return_value
    mock_live_instance.__enter__.return_value = mock_live_instance

    async def gen():
        yield "Hello"
        yield " World"

    asyncio.run(ui.display_stream(gen()))

    assert mock_live.call_count == 1
    assert mock_live_instance.update.call_count == 2
    mock_console.return_value.print.assert_called_once() # Final newline

@pytest.mark.parametrize("data, expected_columns, expected_rows, title", [
    (
        pd.DataFrame(),
        [],
        [],
        None
    ),
    (
        pd.DataFrame({"A": [1, 2], "B": ["x", "y"]}),
        [("A", "right", "green"), ("B", "left", "cyan")],
        [["1", "x"], ["2", "y"]],
        "Test Title"
    ),
    (
        pd.DataFrame({"Views": [100], "retention": ["high"]}), # Case sensitive check for Views
        [("Views", "right", "green"), ("retention", "left", "cyan")], # 'retention' is not 'Retention'
        [["100", "high"]],
        None
    ),
     (
        pd.DataFrame({"Retention": [100], "Retention (%)": [0.5]}),
        [("Retention", "right", "green"), ("Retention (%)", "right", "green")],
        [["100.0", "0.5"]], # iterrows converts ints to floats in mixed-type rows
        None
    ),
])
def test_display_table(
    ui: RichConsoleUI,
    mock_console: MagicMock,
    mock_table: MagicMock,
    data: pd.DataFrame,
    expected_columns: List[Tuple[str, str, str]],
    expected_rows: List[List[str]],
    title: Optional[str]
) -> None:
    ui.display_table(data, title=title)

    if data.empty:
        mock_console.return_value.print.assert_called_with("[italic dim]No data available.[/italic dim]")
        mock_table.assert_not_called()
    else:
        mock_table.assert_called_with(title=title, box=box.ROUNDED)
        table_instance = mock_table.return_value

        # Verify columns
        assert table_instance.add_column.call_count == len(expected_columns)
        for i, (col_name, justify, style) in enumerate(expected_columns):
            args, kwargs = table_instance.add_column.call_args_list[i]
            assert args[0] == col_name
            assert kwargs["justify"] == justify
            assert kwargs["style"] == style

        # Verify rows
        assert table_instance.add_row.call_count == len(expected_rows)
        for i, row in enumerate(expected_rows):
            args, _ = table_instance.add_row.call_args_list[i]
            assert list(args) == row

        mock_console.return_value.print.assert_called_with(table_instance)
