"""
Tests for RichConsoleUI implementation.
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, call
from pytest_mock import MockerFixture
from typing import List, Tuple, Dict, Any
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console(mocker: MockerFixture) -> MagicMock:
    """Mock the rich Console class."""
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table_cls(mocker: MockerFixture) -> MagicMock:
    """Mock the rich Table class."""
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def ui(mock_console: MagicMock) -> RichConsoleUI:
    """Fixture for RichConsoleUI."""
    return RichConsoleUI()

def test_display_table_empty(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    """Test displaying an empty DataFrame."""
    df = pd.DataFrame()
    ui.display_table(df)

    mock_console.return_value.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("data, expected_columns", [
    # Case: Numeric column -> Right, Green
    (
        {"Values": [1, 2, 3]},
        [("Values", "right", "green")]
    ),
    # Case: String column -> Left, Cyan
    (
        {"Names": ["A", "B", "C"]},
        [("Names", "left", "cyan")]
    ),
    # Case: Special column "Views" -> Right, Green
    (
        {"Views": ["100", "200"]},
        [("Views", "right", "green")]
    ),
    # Case: Special column "Retention" -> Right, Green
    (
        {"Retention": ["50%", "60%"]},
        [("Retention", "right", "green")]
    ),
    # Case: Special column "Retention (%)" -> Right, Green
    (
        {"Retention (%)": [0.5, 0.6]},
        [("Retention (%)", "right", "green")]
    ),
    # Case: Mixed columns
    (
        {
            "ID": ["1", "2"],
            "Score": [10, 20],
            "Views": [100, 200]
        },
        [
            ("ID", "left", "cyan"),
            ("Score", "right", "green"),
            ("Views", "right", "green")
        ]
    )
])
def test_display_table_columns(
    ui: RichConsoleUI,
    mock_table_cls: MagicMock,
    mock_console: MagicMock,
    data: Dict[str, List[Any]],
    expected_columns: List[Tuple[str, str, str]]
) -> None:
    """Test that table columns are formatted correctly based on type and name."""
    df = pd.DataFrame(data)
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df)

    # Verify Table was created
    mock_table_cls.assert_called_once()

    # Verify columns were added with correct styling
    assert mock_table_instance.add_column.call_count == len(expected_columns)

    # Check each add_column call
    calls = mock_table_instance.add_column.call_args_list
    for i, col_name in enumerate(df.columns):
        # Find expected config for this column
        # Note: We iterate expected_columns to find the matching name
        expected = next(config for name, *config in expected_columns if name == col_name)
        expected_justify, expected_style = expected

        assert calls[i] == call(str(col_name), justify=expected_justify, style=expected_style)

    # Verify table was printed
    mock_console.return_value.print.assert_called_with(mock_table_instance)

@pytest.mark.parametrize("data, expected_rows", [
    # Case: Simple strings
    (
        {"Col1": ["A", "B"]},
        [["A"], ["B"]]
    ),
    # Case: Integers converted to strings
    (
        {"Col1": [1, 2]},
        [["1"], ["2"]]
    ),
    # Case: Floats converted to strings
    (
        {"Col1": [1.5, 2.5]},
        [["1.5"], ["2.5"]]
    ),
    # Case: None values converted to 'None' or 'NaN' depending on pandas behavior
    # Pandas often converts None to NaN even in object columns depending on construction.
    # We observed 'nan' in the test environment.
    (
        {"Col1": [None, "Text"]},
        [["nan"], ["Text"]]
    ),
    # Case: Mixed types in a row
    (
        {"A": [1], "B": ["X"]},
        [["1", "X"]]
    )
])
def test_display_table_rows(
    ui: RichConsoleUI,
    mock_table_cls: MagicMock,
    mock_console: MagicMock,
    data: Dict[str, List[Any]],
    expected_rows: List[List[str]]
) -> None:
    """Test that data rows are correctly added to the table."""
    df = pd.DataFrame(data)
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df)

    assert mock_table_instance.add_row.call_count == len(expected_rows)

    calls = mock_table_instance.add_row.call_args_list
    for i, expected_row in enumerate(expected_rows):
        # calls[i].args should match expected_row
        assert list(calls[i][0]) == expected_row
