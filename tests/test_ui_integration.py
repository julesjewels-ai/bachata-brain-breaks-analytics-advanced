import pytest
from unittest.mock import MagicMock
import pandas as pd
from src.core.app import BachataAnalyticsApp
from src.core.interfaces import UserInterface

def test_app_calls_ui_methods():
    # Arrange
    mock_ui = MagicMock(spec=UserInterface)
    # Mock context manager for display_status
    mock_ui.display_status.return_value.__enter__.return_value = None

    app = BachataAnalyticsApp(ui=mock_ui)

    # Act
    # We run the full pipeline (simulation)
    app.run()

    # Assert
    # Check header
    mock_ui.display_header.assert_called_with("Bachata Brain Breaks Analytics")

    # Check status was used (at least once for ingestion)
    mock_ui.display_status.assert_any_call("Ingesting channel data...")

    # Check messages
    mock_ui.display_message.assert_called()

    # Check dataframes were displayed (Anomalies)
    assert mock_ui.display_dataframe.called

    # Verify at least one call passed a DataFrame
    for call in mock_ui.display_dataframe.call_args_list:
        args, _ = call
        if len(args) > 0 and isinstance(args[0], pd.DataFrame):
            break
    else:
        pytest.fail("display_dataframe was never called with a DataFrame")
