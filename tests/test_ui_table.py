import pytest
import pandas as pd
from unittest.mock import call
from src.core.ui import RichConsoleUI
from rich import box

@pytest.fixture
def mock_console(mocker):
    return mocker.Mock()

@pytest.fixture
def ui(mock_console):
    return RichConsoleUI(console=mock_console)

@pytest.fixture
def mock_table(mocker):
    # Patch rich.table.Table so we can inspect it
    return mocker.patch("src.core.ui.Table")

def test_display_table_empty(ui, mock_console, mock_table):
    df = pd.DataFrame()
    ui.display_table(df)

    # Should check empty
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")
    # Should not create table
    mock_table.assert_not_called()

def test_display_table_numeric_columns(ui, mock_console, mock_table):
    df = pd.DataFrame({'A': [1, 2], 'B': [3.0, 4.0]})
    # Mock the table instance
    table_instance = mock_table.return_value

    ui.display_table(df)

    # Check Table instantiation
    mock_table.assert_called_with(title=None, box=box.ROUNDED)

    # Check columns
    # A is numeric (int)
    table_instance.add_column.assert_any_call('A', justify='right', style='green')
    # B is numeric (float)
    table_instance.add_column.assert_any_call('B', justify='right', style='green')

    # Check rows
    # Note: row values are stringified
    table_instance.add_row.assert_has_calls([
        call('1', '3.0'),
        call('2', '4.0')
    ])

    # Check print
    mock_console.print.assert_called_with(table_instance)

def test_display_table_special_columns(ui, mock_console, mock_table):
    df = pd.DataFrame({
        'Views': [100],
        'Retention': [50],
        'Retention (%)': [0.5],
        'Other': ['foo']
    })
    table_instance = mock_table.return_value

    ui.display_table(df)

    # Views, Retention, Retention (%) should be right/green
    table_instance.add_column.assert_any_call('Views', justify='right', style='green')
    table_instance.add_column.assert_any_call('Retention', justify='right', style='green')
    table_instance.add_column.assert_any_call('Retention (%)', justify='right', style='green')

    # Other should be left/cyan
    table_instance.add_column.assert_any_call('Other', justify='left', style='cyan')

def test_display_table_string_columns(ui, mock_console, mock_table):
    df = pd.DataFrame({'Name': ['Alice', 'Bob']})
    table_instance = mock_table.return_value

    ui.display_table(df)

    table_instance.add_column.assert_called_with('Name', justify='left', style='cyan')
    table_instance.add_row.assert_has_calls([
        call('Alice'),
        call('Bob')
    ])

def test_display_table_none_values(ui, mock_console, mock_table):
    # Use object dtype to preserve None for numeric-looking column if intended,
    # but here we test standard mixed dataframe behavior.

    df_mixed = pd.DataFrame({'A': [1, None], 'B': ['x', None]})

    table_instance = mock_table.return_value
    ui.display_table(df_mixed)

    # 'A' is numeric (float because of NaN), so right/green
    # 'B' is object, so left/cyan

    table_instance.add_column.assert_any_call('A', justify='right', style='green')
    table_instance.add_column.assert_any_call('B', justify='left', style='cyan')

    # Check rows
    # 1 becomes '1.0' because column is float
    # None in A becomes 'nan'
    # 'x' is 'x'
    # None in B is 'None'

    table_instance.add_row.assert_has_calls([
        call('1.0', 'x'),
        call('nan', 'None')
    ])

@pytest.mark.parametrize("input_data,expected_cols,expected_rows", [
    (
        {'Col1': [10]},
        [('Col1', 'right', 'green')],
        [('10',)]
    ),
    (
        {'Col1': ['text']},
        [('Col1', 'left', 'cyan')],
        [('text',)]
    ),
])
def test_display_table_parametrized(ui, mock_console, mock_table, input_data, expected_cols, expected_rows):
    df = pd.DataFrame(input_data)
    table_instance = mock_table.return_value

    ui.display_table(df)

    for col, just, style in expected_cols:
        table_instance.add_column.assert_any_call(col, justify=just, style=style)

    calls = [call(*row) for row in expected_rows]
    table_instance.add_row.assert_has_calls(calls)
