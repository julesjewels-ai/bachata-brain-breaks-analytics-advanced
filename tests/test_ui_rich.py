"""
Unit tests for RichConsoleUI using pytest and pytest-mock.
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock
from pytest_mock import MockerFixture
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console(mocker: MockerFixture) -> MagicMock:
    """Mocks the internal rich.console.Console."""
    # We patch the class so that when RichConsoleUI instantiates it, it gets our mock
    mock_cls = mocker.patch("src.core.ui.Console", autospec=True)
    return mock_cls.return_value

@pytest.fixture
def ui(mock_console: MagicMock) -> RichConsoleUI:
    """Returns a RichConsoleUI instance with a mocked console."""
    return RichConsoleUI()

def test_display_table_empty(ui: RichConsoleUI, mock_console: MagicMock) -> None:
    """Test display_table with an empty DataFrame."""
    df = pd.DataFrame()
    ui.display_table(df)
    mock_console.print.assert_called_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("col_name, col_data, expected_justify, expected_style", [
    ("Title", ["Video A"], "left", "cyan"),         # String -> Left, Cyan
    ("Views", [1000], "right", "green"),            # "Views" -> Right, Green
    ("Retention", [50.5], "right", "green"),        # "Retention" -> Right, Green
    ("Retention (%)", [95.0], "right", "green"),    # "Retention (%)" -> Right, Green
    ("Score", [10], "right", "green"),              # Numeric -> Right, Green
    ("Tags", ["Bachata"], "left", "cyan"),          # Other String -> Left, Cyan
])
def test_display_table_columns(
    ui: RichConsoleUI,
    mock_console: MagicMock,
    mocker: MockerFixture,
    col_name: str,
    col_data: list,
    expected_justify: str,
    expected_style: str
) -> None:
    """Test display_table column formatting logic."""
    # Mock Table to inspect add_column calls
    mock_table_cls = mocker.patch("src.core.ui.Table", autospec=True)
    mock_table_instance = mock_table_cls.return_value

    df = pd.DataFrame({col_name: col_data})
    ui.display_table(df)

    # Verify Table creation
    mock_table_cls.assert_called_once()

    # Verify add_column was called with correct arguments
    mock_table_instance.add_column.assert_called_with(
        col_name,
        justify=expected_justify,
        style=expected_style
    )

    # Verify add_row was called with stringified data
    expected_row_val = str(col_data[0])
    mock_table_instance.add_row.assert_called_with(expected_row_val)

    # Verify console.print was called with the table
    mock_console.print.assert_called_with(mock_table_instance)

def test_display_table_mixed_columns(ui: RichConsoleUI, mock_console: MagicMock, mocker: MockerFixture) -> None:
    """Test display_table with multiple mixed columns."""
    mock_table_cls = mocker.patch("src.core.ui.Table", autospec=True)
    mock_table_instance = mock_table_cls.return_value

    df = pd.DataFrame({
        "Title": ["Video A"],
        "Views": [100]
    })

    ui.display_table(df)

    # Check calls order matters or use any_call
    # Since dict order is preserved in Python 3.7+, we can expect calls in order
    assert mock_table_instance.add_column.call_count == 2

    # Verify Title column
    mock_table_instance.add_column.assert_any_call("Title", justify="left", style="cyan")

    # Verify Views column
    mock_table_instance.add_column.assert_any_call("Views", justify="right", style="green")

    # Verify row
    mock_table_instance.add_row.assert_called_with("Video A", "100")
