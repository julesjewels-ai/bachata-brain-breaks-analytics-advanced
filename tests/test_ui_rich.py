import pytest
import pandas as pd
import asyncio
from unittest.mock import MagicMock, call
from src.core.ui import RichConsoleUI
from pytest_mock import MockerFixture
from typing import Any, Dict, List, Optional

@pytest.fixture
def mock_console(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def mock_live(mocker: MockerFixture) -> MagicMock:
    return mocker.patch("src.core.ui.Live")

@pytest.mark.parametrize("data_dict, title, expected_calls", [
    # Case 1: Empty DataFrame
    ({}, None, {"empty": True}),

    # Case 2: Numeric DataFrame
    ({"A": [1, 2]}, None, {
        "empty": False,
        "title": None,
        "columns": [("A", "right", "green")],
        "rows": [("1",), ("2",)]
    }),

    # Case 3: Special Column Names (Views, Retention)
    ({"Views": [100], "Retention": ["50%"]}, "My Title", {
        "empty": False,
        "title": "My Title",
        "columns": [("Views", "right", "green"), ("Retention", "right", "green")],
        "rows": [("100", "50%")]
    }),

    # Case 4: Text DataFrame
    ({"Name": ["Video1"]}, None, {
        "empty": False,
        "title": None,
        "columns": [("Name", "left", "cyan")],
        "rows": [("Video1",)]
    }),

    # Case 5: Mixed DataFrame
    ({"Name": ["Video1"], "Views": [100]}, None, {
        "empty": False,
        "title": None,
        "columns": [("Name", "left", "cyan"), ("Views", "right", "green")],
        "rows": [("Video1", "100")]
    }),
])
def test_display_table(
    mock_console: MagicMock,
    mock_table: MagicMock,
    data_dict: Dict[str, List[Any]],
    title: Optional[str],
    expected_calls: Dict[str, Any]
) -> None:
    ui = RichConsoleUI()
    # Inject mock console
    ui.console = mock_console.return_value

    df = pd.DataFrame(data_dict)

    ui.display_table(df, title=title)

    if expected_calls.get("empty"):
        ui.console.print.assert_called_with("[italic dim]No data available.[/italic dim]")
        mock_table.assert_not_called()
    else:
        # Check Table instantiation
        expected_title = expected_calls.get("title")
        mock_table.assert_called_once()
        _, kwargs = mock_table.call_args
        assert kwargs.get("title") == expected_title

        table_instance = mock_table.return_value

        # Check Columns
        expected_columns = expected_calls["columns"]
        assert table_instance.add_column.call_count == len(expected_columns)

        # We check that each expected column was added.
        # Since DataFrame column order is preserved in recent pandas/python versions,
        # we can check order or just existence.
        for name, justify, style in expected_columns:
            table_instance.add_column.assert_any_call(str(name), justify=justify, style=style)

        # Check Rows
        expected_rows = expected_calls["rows"]
        assert table_instance.add_row.call_count == len(expected_rows)
        for row in expected_rows:
             table_instance.add_row.assert_any_call(*row)

        # Check Console Print
        ui.console.print.assert_called_with(table_instance)

def test_display_stream(mock_console: MagicMock, mock_live: MagicMock) -> None:
    # Setup Mock Live
    mock_live_instance = mock_live.return_value
    mock_live_context = MagicMock()
    mock_live_instance.__enter__.return_value = mock_live_context

    ui = RichConsoleUI()
    ui.console = mock_console.return_value

    async def sample_generator():
        yield "Hello"
        yield " "
        yield "World"

    # Run the async method
    asyncio.run(ui.display_stream(sample_generator()))

    # Verify Live was used
    mock_live.assert_called_once()
    _, kwargs = mock_live.call_args
    assert kwargs.get("console") == ui.console

    # Verify updates happened
    # 3 chunks -> 3 updates
    assert mock_live_context.update.call_count == 3

    # Verify final newline
    # assert ui.console.print.called # This might be called multiple times by Live or other things
    # The last call should be empty print()
    ui.console.print.assert_called()

def test_simple_displays(mock_console: MagicMock) -> None:
    ui = RichConsoleUI()
    ui.console = mock_console.return_value

    ui.display_header("Header")
    ui.console.print.assert_called()

    ui.display_section("Section")
    ui.console.print.assert_called_with("\n[bold cyan]--- Section ---[/bold cyan]")

    ui.display_status("Status")
    ui.console.print.assert_called_with("[yellow]Status[/yellow]")

    ui.display_error("Error msg")
    ui.console.print.assert_called_with("[bold red]Error:[/bold red] Error msg")

    ui.display_success("Success")
    ui.console.print.assert_called_with("[bold green]✔ Success[/bold green]")

    ui.display_info("Info")
    ui.console.print.assert_called_with("[blue]ℹ Info[/blue]")

    ui.display_message("Msg")
    ui.console.print.assert_called_with("Msg")

def test_loading(mock_console: MagicMock) -> None:
    ui = RichConsoleUI()
    ui.console = mock_console.return_value

    ctx = ui.loading("Loading...")
    ui.console.status.assert_called_with("Loading...", spinner="dots")
    assert ctx == ui.console.status.return_value
