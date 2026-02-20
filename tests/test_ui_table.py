import pytest
from unittest.mock import Mock, call
from typing import AsyncGenerator
import pandas as pd
from rich import box
from pytest_mock import MockerFixture
from src.core.ui import RichConsoleUI

@pytest.fixture
def mock_console(mocker: MockerFixture) -> Mock:
    """Mock the Console class to prevent actual output."""
    return mocker.patch("src.core.ui.Console")

@pytest.fixture
def ui(mock_console: Mock) -> RichConsoleUI:
    """Fixture for RichConsoleUI with mocked Console."""
    return RichConsoleUI()

class TestRichConsoleUI:
    """Test suite for RichConsoleUI."""

    def test_display_table_empty(self, ui: RichConsoleUI) -> None:
        """Test display_table with an empty DataFrame."""
        df = pd.DataFrame()
        ui.display_table(df)

        # Assert
        # cast(Mock, ui.console).print.assert_called_with(...)
        # But ui.console is typed as Console in RichConsoleUI.
        # Since we mocked it, it's actually a Mock object at runtime.
        # We can use 'type: ignore' or cast. Let's use simpler approach for now.
        ui.console.print.assert_called_with("[italic dim]No data available.[/italic dim]") # type: ignore

    def test_display_table_populated(self, ui: RichConsoleUI, mocker: MockerFixture) -> None:
        """Test display_table with a populated DataFrame covering styling logic."""
        # Mock Table class
        mock_table_cls = mocker.patch("src.core.ui.Table")
        mock_table = mock_table_cls.return_value

        # Create test data
        data = {
            "Name": ["Video A", "Video B"],
            "Views": [1000, 500],
            "Retention": [0.75, 0.60],
            "Score": [9.5, 8.0] # Numeric but not named special
        }
        df = pd.DataFrame(data)

        # Act
        ui.display_table(df, title="Test Table")

        # Assert Table creation
        mock_table_cls.assert_called_with(title="Test Table", box=box.ROUNDED)

        # Assert Columns
        # 1. Name: String -> Left, Cyan
        mock_table.add_column.assert_any_call("Name", justify="left", style="cyan")

        # 2. Views: Numeric + Special Name -> Right, Green
        mock_table.add_column.assert_any_call("Views", justify="right", style="green")

        # 3. Retention: Numeric + Special Name -> Right, Green
        mock_table.add_column.assert_any_call("Retention", justify="right", style="green")

        # 4. Score: Numeric -> Right, Green (because it is numeric)
        mock_table.add_column.assert_any_call("Score", justify="right", style="green")

        # Assert Rows
        # Check if add_row was called for each row with stringified values
        expected_calls = [
            call("Video A", "1000", "0.75", "9.5"),
            call("Video B", "500", "0.6", "8.0")
        ]
        mock_table.add_row.assert_has_calls(expected_calls)

        # Assert Print
        ui.console.print.assert_called_with(mock_table) # type: ignore

    @pytest.mark.asyncio
    async def test_display_stream(self, ui: RichConsoleUI, mocker: MockerFixture) -> None:
        """Test display_stream with an async generator."""
        # Mock Live
        mock_live_cls = mocker.patch("src.core.ui.Live")
        mock_live = mock_live_cls.return_value
        mock_live.__enter__.return_value = mock_live

        # Create async generator
        async def sample_generator() -> AsyncGenerator[str, None]:
            yield "Chunk 1"
            yield "Chunk 2"

        # Act
        await ui.display_stream(sample_generator())

        # Assert Live usage
        mock_live_cls.assert_called()
        assert mock_live.update.call_count == 2

        # Assert Final Print
        ui.console.print.assert_called() # type: ignore
