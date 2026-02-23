import pytest
from unittest.mock import Mock
import pandas as pd
from rich.console import Console
from rich.table import Table
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console():
    return Mock(spec=Console)

@pytest.fixture
def ui(mock_console):
    return RichConsoleUI(console=mock_console)

def test_display_table_empty(ui, mock_console):
    """Test display_table with empty DataFrame."""
    df = pd.DataFrame()
    ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name, expected_justify, expected_style, col_data", [
    ("Numeric", "right", "green", [1, 2, 3]),
    ("Views", "right", "green", ["100", "200"]), # String but name matches
    ("Retention", "right", "green", [0.5, 0.6]),
    ("Retention (%)", "right", "green", [50, 60]),
    ("String", "left", "cyan", ["a", "b", "c"]),
    ("Other", "right", "green", [True, False]), # Boolean is numeric in pandas
])
def test_display_table_columns_style(ui, mock_console, col_name, expected_justify, expected_style, col_data):
    """Test column justification and style based on name and type."""
    df = pd.DataFrame({col_name: col_data})
    ui.display_table(df)

    # Get the Table object passed to print
    args, _ = mock_console.print.call_args
    assert len(args) == 1
    table = args[0]
    assert isinstance(table, Table)

    # Check the column properties
    assert len(table.columns) == 1
    col = table.columns[0]
    assert col.justify == expected_justify
    assert col.style == expected_style
    assert col.header == col_name

def test_display_table_rows(ui, mock_console):
    """Test that rows are added correctly and converted to strings."""
    df = pd.DataFrame({
        "Col1": [1, 2],
        "Col2": ["a", "b"]
    })
    ui.display_table(df)

    args, _ = mock_console.print.call_args
    table = args[0]

    # Check columns content
    cols = table.columns
    assert len(cols) == 2

    col1_cells = list(cols[0].cells)
    col2_cells = list(cols[1].cells)

    # RichConsoleUI converts to string
    assert col1_cells == ["1", "2"]
    assert col2_cells == ["a", "b"]

def test_display_table_title(ui, mock_console):
    """Test that title is passed to Table."""
    df = pd.DataFrame({"A": [1]})
    title = "Test Table"
    ui.display_table(df, title=title)

    args, _ = mock_console.print.call_args
    table = args[0]
    assert table.title == title
