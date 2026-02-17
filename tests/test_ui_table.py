import pytest
from unittest.mock import Mock
import pandas as pd
from rich.console import Console
from src.core.ui import RichConsoleUI
from pytest_mock import MockerFixture
from typing import List, Tuple, Optional, Any

@pytest.fixture
def mock_console(mocker: MockerFixture) -> Mock:
    return mocker.create_autospec(Console, instance=True)

@pytest.fixture
def mock_table_class(mocker: MockerFixture) -> Mock:
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def ui(mock_console: Mock) -> RichConsoleUI:
    return RichConsoleUI(console=mock_console)

def test_display_table_empty(ui: RichConsoleUI, mock_console: Mock) -> None:
    """Test that an empty DataFrame results in a specific message."""
    df = pd.DataFrame()
    ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("data, expected_columns", [
    (
        {"Name": ["A"], "Age": [10]},
        [("Name", "left", "cyan"), ("Age", "right", "green")]
    ),
    (
        {"Title": ["T"], "Views": [100]},
        [("Title", "left", "cyan"), ("Views", "right", "green")]
    ),
    (
        {"Title": ["T"], "Retention": [0.5]},
        [("Title", "left", "cyan"), ("Retention", "right", "green")]
    ),
    (
        {"Title": ["T"], "Retention (%)": [50.0]},
        [("Title", "left", "cyan"), ("Retention (%)", "right", "green")]
    ),
    (
        {"Description": ["D"], "Category": ["C"]},
        [("Description", "left", "cyan"), ("Category", "left", "cyan")]
    ),
])
def test_display_table_columns_formatting(
    ui: RichConsoleUI,
    mock_console: Mock,
    mock_table_class: Mock,
    data: dict[str, list[Any]],
    expected_columns: List[Tuple[str, str, str]]
) -> None:
    """Test that columns are correctly formatted based on type and name."""
    df = pd.DataFrame(data)
    ui.display_table(df)

    mock_table_instance = mock_table_class.return_value

    # Verify add_column calls
    assert mock_table_instance.add_column.call_count == len(expected_columns)

    # Check calls in order
    calls = mock_table_instance.add_column.call_args_list
    for i, (exp_name, exp_justify, exp_style) in enumerate(expected_columns):
        args, kwargs = calls[i]
        assert args[0] == exp_name
        assert kwargs["justify"] == exp_justify
        assert kwargs["style"] == exp_style

    # Verify print was called with the table instance
    mock_console.print.assert_called_with(mock_table_instance)

def test_display_table_rows_count(
    ui: RichConsoleUI,
    mock_console: Mock,
    mock_table_class: Mock
) -> None:
    """Test that correct number of rows are added to the table."""
    df = pd.DataFrame({
        "Col1": ["A", "B", "C"],
        "Col2": [1, 2, 3]
    })
    ui.display_table(df)

    mock_table_instance = mock_table_class.return_value
    assert mock_table_instance.add_row.call_count == 3

@pytest.mark.parametrize("val, expected_str", [
    (10, "10"),
    (3.14, "3.14"),
    ("Text", "Text"),
    (None, "None"), # object dtype None -> "None"
])
def test_display_table_row_values(
    ui: RichConsoleUI,
    mock_console: Mock,
    mock_table_class: Mock,
    val: Any,
    expected_str: str
) -> None:
    """Test that values are converted to string in the table."""
    # Ensure object dtype for None test case to avoid float conversion (NaN)
    dtype = object if val is None else None
    df = pd.DataFrame({"Data": [val]}, dtype=dtype)

    ui.display_table(df)

    mock_table_instance = mock_table_class.return_value
    mock_table_instance.add_row.assert_called_once()

    args, _ = mock_table_instance.add_row.call_args
    # args should be a tuple of strings
    assert args[0] == expected_str

def test_display_table_nan_handling(
    ui: RichConsoleUI,
    mock_console: Mock,
    mock_table_class: Mock
) -> None:
    """Test handling of NaN values (float)."""
    df = pd.DataFrame({"Data": [None]}, dtype=float) # Forces NaN
    ui.display_table(df)

    mock_table_instance = mock_table_class.return_value
    mock_table_instance.add_row.assert_called_once()

    args, _ = mock_table_instance.add_row.call_args
    assert args[0] == "nan"
