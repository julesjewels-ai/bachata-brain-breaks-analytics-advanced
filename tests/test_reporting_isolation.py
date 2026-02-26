
import pytest
import pandas as pd
from io import BytesIO
from typing import Dict, Any
from unittest.mock import MagicMock
from pytest_mock import MockerFixture
from src.core.reporting import ExcelReportGenerator
from src.core.interfaces import Visualizer

@pytest.fixture
def mock_visualizer() -> MagicMock:
    """Fixture to mock the Visualizer protocol."""
    return MagicMock(spec=Visualizer)

@pytest.fixture
def mock_writer() -> MagicMock:
    """Fixture to mock pd.ExcelWriter."""
    writer = MagicMock(spec=pd.ExcelWriter)
    writer.book = MagicMock()
    return writer

class TestExcelReportGeneratorVisualInsights:
    """Test suite for ExcelReportGenerator._add_visual_insights logic."""

    @pytest.mark.parametrize("anomalies, expected_call", [
        ({}, False),  # Empty dictionary
        ({'Shorts': pd.DataFrame()}, False),  # Empty DataFrame
        ({'Shorts': pd.DataFrame({'views': [100]})}, False),  # Missing retention column
        ({'Shorts': pd.DataFrame({'retention_avg_pct': [50.0]})}, False),  # Missing views column
        ({'Shorts': pd.DataFrame({'views': [100], 'retention_avg_pct': [50.0]})}, True),  # Happy Path
    ])
    def test_add_visual_insights_conditions(
        self,
        mock_visualizer: MagicMock,
        mock_writer: MagicMock,
        anomalies: Dict[str, pd.DataFrame],
        expected_call: bool,
        mocker: MockerFixture
    ) -> None:
        """
        Verify that _add_visual_insights only proceeds when data is valid.
        """
        # Arrange
        generator = ExcelReportGenerator(visualizer=mock_visualizer)

        # Mocks for PIL and OpenPyXL Image
        mock_pil_open = mocker.patch('src.core.reporting.PILImage.open')
        mock_xl_image = mocker.patch('src.core.reporting.XLImage')

        # Mock visualizer return value
        fake_stream = BytesIO(b'fake_image_bytes')
        mock_visualizer.generate_chart.return_value = fake_stream

        # Act
        generator._add_visual_insights(mock_writer, anomalies)

        # Assert
        if expected_call:
            # Verify chart generation was called
            mock_visualizer.generate_chart.assert_called_once()

            # Verify sheet creation
            mock_writer.book.create_sheet.assert_called_once_with("Visual Insights")

            # Verify image handling
            mock_pil_open.assert_called_once_with(fake_stream)
            mock_xl_image.assert_called_once()

            # Verify image added to sheet
            ws_viz = mock_writer.book.create_sheet.return_value
            ws_viz.add_image.assert_called_once()

            # Verify description text added
            ws_viz.__setitem__.assert_any_call("A25", (
                "Scatter plot showing relationship between "
                "Audience Retention and View Count."
            ))
        else:
            # Verify chart generation was NOT called
            mock_visualizer.generate_chart.assert_not_called()
            mock_writer.book.create_sheet.assert_not_called()

    def test_add_visual_insights_exception_handling(
        self,
        mock_visualizer: MagicMock,
        mock_writer: MagicMock,
        mocker: MockerFixture
    ) -> None:
        """
        Verify that exceptions during visualization are caught and logged.
        """
        # Arrange
        generator = ExcelReportGenerator(visualizer=mock_visualizer)
        anomalies = {
            'Shorts': pd.DataFrame({'views': [100], 'retention_avg_pct': [50.0]})
        }

        # Force an exception
        mock_visualizer.generate_chart.side_effect = Exception("Chart failed")

        # Spy on logger
        mock_logger = mocker.patch('src.core.reporting.logger')

        # Act
        generator._add_visual_insights(mock_writer, anomalies)

        # Assert
        mock_logger.warning.assert_called_once_with(
            "Failed to generate visualization: Chart failed"
        )
        # Should NOT raise exception further up
