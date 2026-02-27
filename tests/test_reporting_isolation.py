import pytest
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from typing import Dict, Any
from io import BytesIO
from src.core.reporting import ExcelReportGenerator
from src.core.interfaces import Visualizer

class TestExcelReportGeneratorVisualInsights:
    @pytest.fixture
    def mock_visualizer(self) -> Mock:
        return Mock(spec=Visualizer)

    @pytest.fixture
    def generator(self, mock_visualizer: Mock) -> ExcelReportGenerator:
        return ExcelReportGenerator(visualizer=mock_visualizer)

    @pytest.fixture
    def mock_writer(self) -> Mock:
        writer = Mock(spec=pd.ExcelWriter)
        writer.book = MagicMock()
        writer.book.create_sheet.return_value = MagicMock()  # Mock worksheet
        return writer

    @pytest.mark.parametrize("anomalies_input", [
        {},
        {'test': pd.DataFrame()},
        {'test': pd.DataFrame({'views': [100]})},  # Missing retention_avg_pct
    ])
    def test_visual_insights_early_exit(
        self,
        generator: ExcelReportGenerator,
        mock_writer: Mock,
        mock_visualizer: Mock,
        anomalies_input: Dict[str, pd.DataFrame]
    ) -> None:
        """Test early exit conditions for _add_visual_insights."""
        generator._add_visual_insights(mock_writer, anomalies_input)

        mock_visualizer.generate_chart.assert_not_called()
        mock_writer.book.create_sheet.assert_not_called()

    @patch('src.core.reporting.PILImage')
    @patch('src.core.reporting.XLImage')
    def test_successful_visualization(
        self,
        mock_xl_image: Mock,
        mock_pil_image: Mock,
        generator: ExcelReportGenerator,
        mock_writer: Mock,
        mock_visualizer: Mock
    ) -> None:
        """Test successful chart generation and embedding."""
        df = pd.DataFrame({
            'views': [100, 200],
            'retention_avg_pct': [50.5, 60.0]
        })
        anomalies = {'test': df}

        # Setup mocks
        mock_stream = BytesIO(b"fake_image_data")
        mock_visualizer.generate_chart.return_value = mock_stream

        mock_pil_obj = Mock()
        mock_pil_image.open.return_value = mock_pil_obj

        mock_xl_obj = Mock()
        mock_xl_image.return_value = mock_xl_obj

        mock_ws = mock_writer.book.create_sheet.return_value

        # Execute
        generator._add_visual_insights(mock_writer, anomalies)

        # Verify
        mock_visualizer.generate_chart.assert_called_once()
        mock_writer.book.create_sheet.assert_called_with("Visual Insights")
        mock_pil_image.open.assert_called_with(mock_stream)
        mock_xl_image.assert_called_with(mock_pil_obj)
        mock_ws.add_image.assert_called_with(mock_xl_obj, "A1")

        # Verify setitem called for A25
        assert any(call.args[0] == "A25" for call in mock_ws.__setitem__.mock_calls)

    def test_visualization_generation_error(
        self,
        generator: ExcelReportGenerator,
        mock_writer: Mock,
        mock_visualizer: Mock,
        caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handling of error during chart generation."""
        df = pd.DataFrame({
            'views': [100],
            'retention_avg_pct': [50.0]
        })
        anomalies = {'test': df}

        mock_visualizer.generate_chart.side_effect = Exception("Generation failed")

        # Execute
        generator._add_visual_insights(mock_writer, anomalies)

        # Verify logger warning
        assert "Failed to generate visualization: Generation failed" in caplog.text
        mock_writer.book.create_sheet.assert_not_called()

    @patch('src.core.reporting.PILImage')
    def test_image_processing_error(
        self,
        mock_pil_image: Mock,
        generator: ExcelReportGenerator,
        mock_writer: Mock,
        mock_visualizer: Mock,
        caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test handling of error during image processing."""
        df = pd.DataFrame({
            'views': [100],
            'retention_avg_pct': [50.0]
        })
        anomalies = {'test': df}

        mock_visualizer.generate_chart.return_value = BytesIO(b"data")
        mock_pil_image.open.side_effect = Exception("Image open failed")

        # Execute
        generator._add_visual_insights(mock_writer, anomalies)

        # Verify logger warning
        assert "Failed to generate visualization: Image open failed" in caplog.text
        mock_writer.book.create_sheet.assert_called_with("Visual Insights")
