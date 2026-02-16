import pytest
import pandas as pd
from unittest.mock import Mock, call
from src.core.ui import RichConsoleUI
from rich.console import Console

@pytest.fixture
def mock_console(mocker):
    return mocker.Mock(spec=Console)

@pytest.fixture
def ui(mock_console):
    return RichConsoleUI(console=mock_console)

@pytest.fixture
def mock_table_cls(mocker):
    return mocker.patch("src.core.ui.Table")

@pytest.mark.parametrize("input_df, expected_print_arg_type, expected_columns, expected_rows", [
    # Case 1: Empty DataFrame
    (pd.DataFrame(), str, [], []),

    # Case 2: Numeric Column
    (pd.DataFrame({"Count": [10, 20]}), "Table", [("Count", "right", "green")], [("10",), ("20",)]),

    # Case 3: "Views" Column (Special handling)
    (pd.DataFrame({"Views": ["100", "200"]}), "Table", [("Views", "right", "green")], [("100",), ("200",)]),

    # Case 4: String Column (Default handling)
    (pd.DataFrame({"Name": ["Alice", "Bob"]}), "Table", [("Name", "left", "cyan")], [("Alice",), ("Bob",)]),

    # Case 5: Mixed Types (String conversion)
    (pd.DataFrame({"ID": [1], "Name": ["A"]}), "Table",
     [("ID", "right", "green"), ("Name", "left", "cyan")],
     [("1", "A")]),

    # Case 6: None Values (as object to preserve None initially)
    # Using dtype=object to ensure None is preserved as NoneType in the DataFrame
    (pd.DataFrame({"Val": [None]}, dtype=object), "Table", [("Val", "left", "cyan")], [("None",)]),

    # Case 6b: NaN Values (float) - Coerced from None if not object
    (pd.DataFrame({"Val": [float("nan")]}), "Table", [("Val", "right", "green")], [("nan",)]),
])
def test_display_table_structure(
    ui, mock_console, mock_table_cls, input_df, expected_print_arg_type, expected_columns, expected_rows
):
    # Arrange
    mock_table_instance = mock_table_cls.return_value

    # Act
    ui.display_table(input_df)

    # Assert
    if expected_print_arg_type == str:
        # Expect "No data" message
        assert mock_console.print.called
        args, _ = mock_console.print.call_args
        assert "[italic dim]No data available.[/italic dim]" in args[0], "Expected 'No data' message"
        assert not mock_table_cls.called, "Table should not be instantiated for empty DataFrame"
    else:
        # Expect Table creation and printing
        assert mock_table_cls.called, "Table should be instantiated"

        # Verify columns
        for col_name, justify, style in expected_columns:
            mock_table_instance.add_column.assert_any_call(str(col_name), justify=justify, style=style)

        # Verify rows
        # The mock doesn't store rows in a list unless we inspect call_args_list
        assert mock_table_instance.add_row.call_count == len(expected_rows), f"Expected {len(expected_rows)} rows"

        # Use simple iteration to verify calls if order matches
        # or assert_any_call if order is not strict (though rows should be ordered)
        # Here we assume order matters for rows
        calls = mock_table_instance.add_row.call_args_list
        for i, row in enumerate(expected_rows):
             assert calls[i] == call(*row), f"Row {i} mismatch. Expected {row}, got {calls[i]}"

        # Verify print was called with the table
        mock_console.print.assert_called_with(mock_table_instance)
