import pytest
import pandas as pd
from unittest.mock import MagicMock
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console(mocker):
    """Mock the Console class used in RichConsoleUI."""
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def mock_table_cls(mocker):
    """Mock the Table class used in RichConsoleUI."""
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def ui(mock_console):
    """Fixture for RichConsoleUI instance."""
    # The __init__ calls Console(), so we need the mock to be active
    return RichConsoleUI()

@pytest.mark.parametrize("data_dict, title, expected_columns, expected_rows, expected_message", [
    # Case 1: Empty DataFrame
    (
        {},
        None,
        [],
        [],
        "[italic dim]No data available.[/italic dim]"
    ),
    # Case 2: Standard DataFrame with strings
    (
        {"Name": ["Alice", "Bob"], "City": ["NY", "LA"]},
        "User Data",
        [
            {"name": "Name", "justify": "left", "style": "cyan"},
            {"name": "City", "justify": "left", "style": "cyan"}
        ],
        [
            ["Alice", "NY"],
            ["Bob", "LA"]
        ],
        None
    ),
    # Case 3: Numeric Columns (Right aligned, Green)
    (
        {"Age": [25, 30], "Score": [88.5, 92.0]},
        "Stats",
        [
            {"name": "Age", "justify": "right", "style": "green"},
            {"name": "Score", "justify": "right", "style": "green"}
        ],
        [
            ["25", "88.5"],
            ["30", "92.0"]
        ],
        None
    ),
    # Case 4: Special Columns "Views", "Retention" (Right aligned, Green)
    (
        {"Views": ["100k", "200k"], "Retention": ["High", "Low"]},
        "Metrics",
        [
            {"name": "Views", "justify": "right", "style": "green"},
            {"name": "Retention", "justify": "right", "style": "green"}
        ],
        [
            ["100k", "High"],
            ["200k", "Low"]
        ],
        None
    ),
    # Case 5: Mixed Data Types and None handling
    (
        {"ID": [1, 2], "Comment": ["Great", None]},
        None,
        [
            {"name": "ID", "justify": "right", "style": "green"},
            {"name": "Comment", "justify": "left", "style": "cyan"}
        ],
        [
            ["1", "Great"],
            ["2", "nan"]  # pandas converts None to NaN/nan for object columns often, or we check string conversion
        ],
        None
    ),
])
def test_display_table(
    ui,
    mock_table_cls,
    data_dict,
    title,
    expected_columns,
    expected_rows,
    expected_message
):
    """
    Test display_table with various DataFrame configurations.
    """
    # Arrange
    df = pd.DataFrame(data_dict)

    # Act
    ui.display_table(df, title=title)

    # Assert
    if expected_message:
        # If we expect a message (empty data case)
        ui.console.print.assert_called_with(expected_message)
        mock_table_cls.assert_not_called()
    else:
        # Verify Table creation
        mock_table_cls.assert_called_once_with(title=title, box=pytest.importorskip("rich.box").ROUNDED)
        table_instance = mock_table_cls.return_value

        # Verify Columns
        # Note: Order matters in our check, and DataFrame columns order is preserved from dict in modern Python
        assert table_instance.add_column.call_count == len(expected_columns), \
            f"Expected {len(expected_columns)} columns, but got {table_instance.add_column.call_count}"

        for i, col_def in enumerate(expected_columns):
            # Check the specific call arguments
            call_args = table_instance.add_column.call_args_list[i]
            assert call_args[0][0] == col_def["name"], \
                f"Column {i} name mismatch: expected {col_def['name']}, got {call_args[0][0]}"
            assert call_args[1]["justify"] == col_def["justify"], \
                f"Column {i} justify mismatch: expected {col_def['justify']}, got {call_args[1]['justify']}"
            assert call_args[1]["style"] == col_def["style"], \
                f"Column {i} style mismatch: expected {col_def['style']}, got {call_args[1]['style']}"

        # Verify Rows
        assert table_instance.add_row.call_count == len(expected_rows), \
            f"Expected {len(expected_rows)} rows, but got {table_instance.add_row.call_count}"

        for i, row_data in enumerate(expected_rows):
            # We use assert_any_call because row order is usually preserved but implementation details (like iteration order) might vary if not careful.
            # However, since we iterate linearly, we expect them.
            # But here we just want to ensure expected row data was added.
            try:
                table_instance.add_row.assert_any_call(*row_data)
            except AssertionError as e:
                raise AssertionError(f"Row {row_data} not found in calls: {table_instance.add_row.call_args_list}") from e

        # Verify Print called with table
        ui.console.print.assert_called_with(table_instance)

def test_display_table_dataframe_none_handling(ui, mock_table_cls):
    """
    Specific test to ensure None values in object columns are stringified as 'None' or 'nan'.
    Pandas behavior varies, so let's verify what happens with explicit None.
    """
    df = pd.DataFrame({"A": [None, "Text"]})
    ui.display_table(df)

    table_instance = mock_table_cls.return_value
    # Depending on pandas version and dtype, None might be 'None' or 'nan'
    # In the parameterized test I assumed 'nan' because pandas often converts object cols with None.
    # Let's inspect what was actually called.

    # We just want to ensure it doesn't crash and adds a string.
    assert table_instance.add_row.call_count == 2, \
        f"Expected 2 rows, got {table_instance.add_row.call_count}"

    # Check first row (which was None)
    args, _ = table_instance.add_row.call_args_list[0]
    assert isinstance(args[0], str), f"Expected string type for cell value, got {type(args[0])}"
    assert args[0] in ["None", "nan"], f"Expected 'None' or 'nan', got '{args[0]}'"
