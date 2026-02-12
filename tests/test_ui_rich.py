import pytest
import pandas as pd
from typing import Any
from unittest.mock import MagicMock
from pytest_mock import MockerFixture
from src.core.ui import RichConsoleUI

@pytest.fixture
def ui(mocker: MockerFixture) -> RichConsoleUI:
    """Fixture to create a RichConsoleUI instance with a mocked Console."""
    # Patch Console class before instantiation to avoid side effects
    mocker.patch("src.core.ui.Console")
    ui = RichConsoleUI()
    # Ensure the instance's console attribute is our mock
    ui.console = mocker.Mock()
    return ui

def test_display_table_empty(ui: RichConsoleUI) -> None:
    """Test that display_table handles empty DataFrames correctly."""
    df = pd.DataFrame()
    ui.display_table(df)
    ui.console.print.assert_called_once_with("[italic dim]No data available.[/italic dim]")

@pytest.mark.parametrize("df_data, col_name, expected_justify, expected_style", [
    ({"A": [1]}, "A", "right", "green"),          # Numeric
    ({"Views": [1]}, "Views", "right", "green"),  # Specific Name
    ({"Retention": [0.5]}, "Retention", "right", "green"), # Specific Name
    ({"Retention (%)": [50]}, "Retention (%)", "right", "green"), # Specific Name
    ({"A": ["text"]}, "A", "left", "cyan"),       # Text
])
def test_display_table_structure(
    ui: RichConsoleUI,
    mocker: MockerFixture,
    df_data: dict[str, list[Any]],
    col_name: str,
    expected_justify: str,
    expected_style: str
) -> None:
    """Test that table columns are created with correct styles and justification."""
    df = pd.DataFrame(df_data)

    # Mock Table class
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df)

    mock_table_instance.add_column.assert_called_with(
        col_name, justify=expected_justify, style=expected_style
    )
    ui.console.print.assert_called_with(mock_table_instance)

def test_display_table_rows(ui: RichConsoleUI, mocker: MockerFixture) -> None:
    """Test that table rows are added with correct string conversions."""
    df = pd.DataFrame({
        "Float": [1.0, None],
        "Bool": [True, False],
        "Obj": ["x", None]
    })

    # Mock Table class
    mock_table_cls = mocker.patch("src.core.ui.Table")
    mock_table_instance = mock_table_cls.return_value

    ui.display_table(df)

    # Expected calls to add_row
    # Row 1: 1.0, True, "x" -> "1.0", "True", "x"
    # Row 2: NaN, False, None -> "nan", "False", "nan"
    # Note: In our environment (Pandas 3.0), mixed types or object columns with None result in 'nan' strings.

    assert mock_table_instance.add_row.call_count == 2
    mock_table_instance.add_row.assert_any_call("1.0", "True", "x")
    mock_table_instance.add_row.assert_any_call("nan", "False", "nan")
