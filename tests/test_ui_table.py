"""
Tests for RichConsoleUI.display_table using parametrization.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import Mock, call, ANY
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console():
    return Mock()

@pytest.fixture
def mock_table_cls(mocker):
    return mocker.patch("src.core.ui.Table")

@pytest.fixture
def ui(mock_console):
    return RichConsoleUI(console=mock_console)

def test_display_table_empty(ui, mock_console):
    """Test that empty dataframe prints 'No data available'."""
    df = pd.DataFrame()
    ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Name", ["Alice"], "left", "cyan"),            # Standard string column
    ("Age", [30], "right", "green"),                # Numeric integer column
    ("Cost", [10.5], "right", "green"),             # Numeric float column
    ("Views", ["1000"], "right", "green"),          # Special column name 'Views' (even if string)
    ("Retention", ["50%"], "right", "green"),       # Special column name 'Retention'
    ("Retention (%)", [0.5], "right", "green"),     # Special column name 'Retention (%)'
    ("Mixed", ["A", 1], "left", "cyan"),            # Mixed type (object) - should default to left/cyan unless name matches
])
def test_display_table_columns_config(ui, mock_table_cls, col_name, col_data, expected_justify, expected_style):
    """Verify column configuration (alignment and style) via parametrization."""
    df = pd.DataFrame({col_name: col_data})

    # We rely on pandas inference for dtype mostly, but 'Age' and 'Cost' will be numeric.

    ui.display_table(df)

    table_instance = mock_table_cls.return_value
    table_instance.add_column.assert_called_with(str(col_name), justify=expected_justify, style=expected_style)

@pytest.mark.parametrize("input_data, dtype, expected_row_calls", [
    # Case 1: Standard Strings
    ({"A": ["val1", "val2"]}, None, [call("val1"), call("val2")]),

    # Case 2: Integer Preservation
    ({"A": [1, 2]}, "int64", [call("1"), call("2")]),

    # Case 3: Float Preservation
    ({"A": [1.5, 2.0]}, "float64", [call("1.5"), call("2.0")]),

    # Case 4: None handling
    # pandas with object column: None -> None. str(None) -> 'None'
    ({"A": [None]}, "object", [call("None")]),

    # Case 5: NaN handling
    # pandas with object column: NaN -> nan. str(nan) -> 'nan'
    ({"A": [np.nan]}, "object", [call("nan")]),

    # Case 6: Mixed types (int and float) in object column
    # If we pass list [1, 1.5] to DF with dtype=object, pandas keeps them as objects? Yes.
    ({"A": [1, 1.5]}, "object", [call("1"), call("1.5")]),
])
def test_display_table_row_rendering(ui, mock_table_cls, input_data, dtype, expected_row_calls):
    """Verify row values are rendered correctly to strings."""
    df = pd.DataFrame(input_data)
    if dtype:
        # If input is object/None, forcing object dtype is tricky if pandas already coerced.
        # But here we create then astype.
        # For mixed types, astype(object) after creation might be too late if inferred as float.
        # So we pass dtype to constructor if possible, or just use astype.
        # For [1, 1.5], pandas infers float. astype(object) keeps them as floats (1.0, 1.5).
        # To strictly test mixed int/float in object column, we must be careful.
        # We can construct DF with dtype=object.
        pass

    # Re-create DF with explicit dtype if provided to ensure correct initial parsing
    if dtype == "object":
         # Use constructor dtype to prevent inference
         df = pd.DataFrame(input_data, dtype=object)
    elif dtype:
         df = df.astype(dtype)

    ui.display_table(df)

    table_instance = mock_table_cls.return_value

    assert table_instance.add_row.call_count == len(expected_row_calls)
    table_instance.add_row.assert_has_calls(expected_row_calls, any_order=False)

def test_display_table_invalid_columns(ui, mock_table_cls):
    """Test safety with invalid column names (spaces, numbers) using itertuples(name=None)."""
    df = pd.DataFrame({'User Name': ['Alice'], '123': ['val']})
    ui.display_table(df)

    table_instance = mock_table_cls.return_value
    assert table_instance.add_row.call_count == 1
    # Check content: columns order is typically alphabetical or insertion order.
    # Dict insertion order is preserved in recent python.
    # So 'User Name' then '123'.
    # Wait, assertions for add_row arguments order matters.
    # We can check any call has these args.
    table_instance.add_row.assert_called_with("Alice", "val")
