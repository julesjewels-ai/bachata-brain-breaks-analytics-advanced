import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO
import pandas as pd
import logging

from src.core.reporting import ExcelReportGenerator
from src.core.interfaces import Visualizer


# A valid minimal PNG signature to satisfy PIL.Image.open
MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00'
    b'\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\n'
    b'IDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00'
    b'\x00IEND\xaeB`\x82'
)


@pytest.fixture
def mock_visualizer() -> Mock:
    return Mock(spec=Visualizer)


@pytest.fixture
def mock_writer() -> MagicMock:
    writer = MagicMock()
    mock_book = MagicMock()
    mock_ws = MagicMock()
    mock_book.create_sheet.return_value = mock_ws
    writer.book = mock_book
    return writer


@pytest.fixture
def valid_df() -> pd.DataFrame:
    return pd.DataFrame({
        'video_id': ['1', '2'],
        'title': ['A', 'B'],
        'views': [100, 1000],
        'retention_avg_pct': [50.0, 90.0]
    })


@pytest.fixture
def invalid_df() -> pd.DataFrame:
    return pd.DataFrame({
        'video_id': ['1', '2'],
        'title': ['A', 'B']
    })


@pytest.mark.parametrize(
    "anomalies_type, expected_outcome",
    [
        ("happy_path", "success"),
        ("empty", "early_exit"),
        ("missing_columns", "early_exit"),
        ("chart_exception", "warning_logged")
    ]
)
def test_add_visual_insights_isolation(
    mock_visualizer: Mock,
    mock_writer: MagicMock,
    valid_df: pd.DataFrame,
    invalid_df: pd.DataFrame,
    anomalies_type: str,
    expected_outcome: str,
    caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    generator = ExcelReportGenerator(visualizer=mock_visualizer)

    anomalies: dict[str, pd.DataFrame] = {}
    if anomalies_type == "happy_path":
        anomalies = {'test': valid_df}
        mock_visualizer.generate_chart.return_value = BytesIO(MINIMAL_PNG)
    elif anomalies_type == "empty":
        anomalies = {}
    elif anomalies_type == "missing_columns":
        anomalies = {'test': invalid_df}
    elif anomalies_type == "chart_exception":
        anomalies = {'test': valid_df}
        mock_visualizer.generate_chart.side_effect = Exception("Simulated chart generation failure")

    # Act
    # We need to patch PIL.Image.open and openpyxl.drawing.image.Image
    # to avoid actual file system / image processing logic.
    with patch('src.core.reporting.PILImage.open') as mock_pil_open, \
         patch('src.core.reporting.XLImage') as mock_xl_image:

        # Setup mocks inside patch context
        mock_pil_img = MagicMock()
        mock_pil_open.return_value = mock_pil_img

        mock_xl_img_instance = MagicMock()
        mock_xl_image.return_value = mock_xl_img_instance

        with caplog.at_level(logging.WARNING):
            generator._add_visual_insights(mock_writer, anomalies)

    # Assert
    mock_ws = mock_writer.book.create_sheet.return_value

    if expected_outcome == "early_exit":
        mock_visualizer.generate_chart.assert_not_called()
        mock_writer.book.create_sheet.assert_not_called()
    elif expected_outcome == "success":
        mock_visualizer.generate_chart.assert_called_once()
        mock_writer.book.create_sheet.assert_called_once_with("Visual Insights")
        mock_ws.add_image.assert_called_once_with(mock_xl_img_instance, "A1")
        mock_ws.__setitem__.assert_any_call(
            "A25",
            "Scatter plot showing relationship between Audience Retention and View Count."
        )
    elif expected_outcome == "warning_logged":
        mock_visualizer.generate_chart.assert_called_once()
        assert "Failed to generate visualization: Simulated chart generation failure" in caplog.text
        mock_writer.book.create_sheet.assert_not_called()
