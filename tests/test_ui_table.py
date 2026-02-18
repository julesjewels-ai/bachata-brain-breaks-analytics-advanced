import pytest
import pandas as pd
from typing import Any, cast
from unittest.mock import Mock
from src.core.ui import RichConsoleUI
from rich.console import Console

@pytest.fixture
def mock_console(mocker: Any) -> Any:
    return mocker.Mock(spec=Console)

@pytest.fixture
def ui(mock_console: Any) -> RichConsoleUI:
    return RichConsoleUI(console=mock_console)

def test_display_table_empty(ui: RichConsoleUI) -> None:
    """Test that empty DataFrame prints 'No data available'."""
    df = pd.DataFrame()
    ui.display_table(df)
    # Cast to Mock to access assert_called_with, since static type is Console
    cast(Mock, ui.console).print.assert_called_with("[italic dim]No data available.[/italic dim]")

def test_display_table_structure(ui: RichConsoleUI, mocker: Any) -> None:
    """Test full table structure: creation, columns, rows, and print."""
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table = mock_table_cls.return_value

    df = pd.DataFrame({
        "Name": ["Video A", "Video B"],
        "Views": [1000, 2000],
        "Retention": [0.5, 0.6]
    })

    ui.display_table(df, title="Test Table")

    # Verify Table initialization
    mock_table_cls.assert_called_once()
    assert mock_table_cls.call_args.kwargs['title'] == "Test Table"

    # Verify columns added
    # "Name" -> left, cyan
    mock_table.add_column.assert_any_call("Name", justify="left", style="cyan")
    # "Views" -> right, green (numeric)
    mock_table.add_column.assert_any_call("Views", justify="right", style="green")
    # "Retention" -> right, green (numeric)
    mock_table.add_column.assert_any_call("Retention", justify="right", style="green")

    # Verify rows added
    mock_table.add_row.assert_any_call("Video A", "1000", "0.5")
    mock_table.add_row.assert_any_call("Video B", "2000", "0.6")

    # Verify console.print called with table
    cast(Mock, ui.console).print.assert_called_with(mock_table)

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Title", ["A", "B"], "left", "cyan"),
    ("Views", [10, 20], "right", "green"),
    ("Retention", [0.5, 0.6], "right", "green"),
    ("Retention (%)", [50, 60], "right", "green"),
    ("RandomNum", [1, 2], "right", "green"),
    ("RandomStr", ["x", "y"], "left", "cyan"),
])
def test_display_table_column_formatting(
    ui: RichConsoleUI,
    mocker: Any,
    col_name: str,
    col_data: list,
    expected_justify: str,
    expected_style: str
) -> None:
    """Test column justification and styling based on name and type."""
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table = mock_table_cls.return_value

    df = pd.DataFrame({col_name: col_data})

    ui.display_table(df)

    mock_table.add_column.assert_called_with(str(col_name), justify=expected_justify, style=expected_style)

def test_display_table_none_values(ui: RichConsoleUI, mocker: Any) -> None:
    """Test handling of None values in DataFrame."""
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table = mock_table_cls.return_value

    # Use object dtype to ensure None is preserved and not converted to NaN (if possible)
    # However, pandas behavior might vary.
    # In a mixed string/None column, it stays object.
    df = pd.DataFrame({"Data": [None, "Value"]}, dtype=object)

    ui.display_table(df)

    calls = mock_table.add_row.call_args_list
    assert len(calls) == 2
    args = [c[0][0] for c in calls]
    assert "Value" in args
    assert "None" in args or "nan" in args
