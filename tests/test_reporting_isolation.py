import pytest
import pandas as pd
from typing import Dict
from io import BytesIO
from unittest.mock import Mock, patch, MagicMock
from pydantic import ValidationError

from src.core.reporting import ReportConfig, ExcelReportGenerator
from src.core.interfaces import Visualizer

# --- ReportConfig Tests ---

@pytest.mark.parametrize("filepath, expected_error", [
    ("valid_report.xlsx", None),
    ("folder/valid_report.xlsx", None),
    ("valid-report_1.xlsx", None),
    ("invalid_extension.txt", "File must be an Excel (.xlsx) file"),
    ("../path_traversal.xlsx", "Path traversal detected"),
    ("folder/../../traversal.xlsx", "Path traversal detected"),
    ("invalid*chars.xlsx", "File path contains invalid characters"),
    ("invalid?chars.xlsx", "File path contains invalid characters"),
])
def test_report_config_validation(filepath: str, expected_error: str | None) -> None:
    if expected_error:
        with pytest.raises(ValidationError) as exc_info:
            ReportConfig(filepath=filepath)
        assert expected_error in str(exc_info.value), f"Expected error {expected_error} not found in {exc_info.value}"
    else:
        config = ReportConfig(filepath=filepath)
        assert config.filepath == filepath, f"Expected filepath {filepath}, got {config.filepath}"


# --- ExcelReportGenerator Tests ---

@pytest.fixture
def mock_visualizer() -> Mock:
    visualizer = Mock(spec=Visualizer)
    # Return a dummy BytesIO for generate_chart
    visualizer.generate_chart.return_value = BytesIO(b"dummy image data")
    return visualizer

@pytest.fixture
def generator(mock_visualizer: Mock) -> ExcelReportGenerator:
    return ExcelReportGenerator(visualizer=mock_visualizer)

@pytest.mark.parametrize("headers, max_row, expected_add_bar_chart", [
    ({"Views": 1, "Video Title": 2}, 2, True),   # Valid case
    ({"Video Title": 2}, 2, False),              # Missing Views
    ({"Views": 1}, 2, False),                    # Missing Video Title
    ({"Views": 1, "Video Title": 2}, 1, False),  # No data (only header)
    ({}, 2, False),                              # No headers
])
def test_add_anomaly_chart_edge_cases(
    generator: ExcelReportGenerator,
    headers: Dict[str, int],
    max_row: int,
    expected_add_bar_chart: bool
) -> None:
    # Arrange
    ws_mock = MagicMock()
    ws_mock.max_row = max_row
    ws_mock.max_column = 5

    with patch('src.core.reporting.ExcelStyler.get_header_map', return_value=headers), \
         patch('src.core.reporting.ChartBuilder') as mock_chart_builder_cls:

        mock_builder_instance = mock_chart_builder_cls.return_value

        # Act
        generator._add_anomaly_chart(ws_mock, "TestType")

        # Assert
        if expected_add_bar_chart:
            mock_builder_instance.add_bar_chart.assert_called_once()
        else:
            mock_chart_builder_cls.assert_not_called()

@pytest.mark.parametrize("anomalies_data, expect_chart, error_trigger", [
    # Valid data, chart expected
    ({"Shorts": pd.DataFrame({"views": [100], "retention_avg_pct": [50.0]})}, True, None),

    # Missing columns
    ({"Shorts": pd.DataFrame({"views": [100]})}, False, None),
    ({"Shorts": pd.DataFrame({"retention_avg_pct": [50.0]})}, False, None),

    # Empty data
    ({}, False, None),
    ({"Shorts": pd.DataFrame()}, False, None),

    # Exception handling
    ({"Shorts": pd.DataFrame({"views": [100], "retention_avg_pct": [50.0]})}, False, "visualizer"),
    ({"Shorts": pd.DataFrame({"views": [100], "retention_avg_pct": [50.0]})}, False, "pil"),
])
def test_add_visual_insights_edge_cases(
    generator: ExcelReportGenerator,
    mock_visualizer: Mock,
    anomalies_data: Dict[str, pd.DataFrame],
    expect_chart: bool,
    error_trigger: str | None,
    caplog: pytest.LogCaptureFixture
) -> None:
    # Arrange
    writer_mock = MagicMock()
    ws_viz_mock = MagicMock()
    writer_mock.book.create_sheet.return_value = ws_viz_mock

    if error_trigger == "visualizer":
        mock_visualizer.generate_chart.side_effect = Exception("Visualizer error")

    with patch('src.core.reporting.PILImage.open') as mock_pil_open, \
         patch('src.core.reporting.XLImage') as mock_xl_image:

        if error_trigger == "pil":
            mock_pil_open.side_effect = Exception("PIL error")

        # Act
        generator._add_visual_insights(writer_mock, anomalies_data)

        # Assert
        if expect_chart:
            mock_visualizer.generate_chart.assert_called_once()
            mock_pil_open.assert_called_once()
            ws_viz_mock.add_image.assert_called_once()
            # Test setting description using assert_any_call if it's set directly as a dict item
            # openpyxl ws["A25"] translates to ws.__setitem__('A25', value)
            # or ws.__setitem__("A25", value)
            found_setitem = False
            for call in ws_viz_mock.__setitem__.call_args_list:
                if call[0][0] == "A25":
                    found_setitem = True
                    break
            assert found_setitem, "Expected description to be set at A25"
        else:
            if error_trigger == "visualizer":
                mock_visualizer.generate_chart.assert_called_once()
                mock_pil_open.assert_not_called()
                assert "Failed to generate visualization: Visualizer error" in caplog.text, "Expected specific error string"
            elif error_trigger == "pil":
                mock_visualizer.generate_chart.assert_called_once()
                mock_pil_open.assert_called_once()
                ws_viz_mock.add_image.assert_not_called()
                assert "Failed to generate visualization: PIL error" in caplog.text, "Expected specific error string"
            else:
                mock_visualizer.generate_chart.assert_not_called()

def test_generate_report(generator: ExcelReportGenerator) -> None:
    # Testing that generate_report delegates correctly to generate_excel
    with patch.object(generator, 'generate_excel') as mock_generate_excel:
        anomalies = {"test": pd.DataFrame()}
        strategy = "strategy"
        filepath = "test.xlsx"

        generator.generate_report(anomalies, strategy, filepath)

        mock_generate_excel.assert_called_once_with(anomalies, strategy, filepath)

@pytest.mark.parametrize("filepath, is_valid_path", [
    ("valid_report.xlsx", True),
    ("../invalid_report.xlsx", False),
])
def test_generate_excel_flow(
    generator: ExcelReportGenerator,
    filepath: str,
    is_valid_path: bool
) -> None:
    anomalies = {
        "Valid": pd.DataFrame({"col": [1]}),
        "Empty": pd.DataFrame()
    }
    strategy = "Test Strategy"

    if not is_valid_path:
        with pytest.raises(ValueError, match="Security validation failed:"):
            generator.generate_excel(anomalies, strategy, filepath)
        return

    with patch('pandas.ExcelWriter') as mock_excel_writer_cls, \
         patch.object(generator, '_create_anomaly_sheet') as mock_create_sheet, \
         patch.object(generator, '_add_anomaly_chart') as mock_add_chart, \
         patch.object(generator, '_add_strategy_sheet') as mock_add_strategy, \
         patch.object(generator, '_add_visual_insights') as mock_add_visuals:

        # Act
        generator.generate_excel(anomalies, strategy, filepath)

        # Assert
        mock_excel_writer_cls.assert_called_once()

        # Verify empty dataframe is skipped (only "Valid" is processed)
        assert mock_create_sheet.call_count == 1, f"Expected 1 call, got {mock_create_sheet.call_count}"
        assert mock_create_sheet.call_args[0][1] == "Valid", "Expected Valid column to be processed"

        mock_add_chart.assert_called_once()
        mock_add_strategy.assert_called_once()
        mock_add_visuals.assert_called_once()


def test_create_anomaly_sheet(generator: ExcelReportGenerator) -> None:
    with patch('pandas.DataFrame.rename') as mock_rename, \
         patch('pandas.DataFrame.to_excel') as mock_to_excel, \
         patch('src.core.reporting.ExcelStyler.apply_header_style') as mock_header, \
         patch('src.core.reporting.ExcelStyler.apply_number_formats') as mock_numbers, \
         patch('src.core.reporting.ExcelStyler.apply_conditional_formatting') as mock_cond, \
         patch('src.core.reporting.ExcelStyler.adjust_column_widths') as mock_widths:

        writer_mock = MagicMock()
        ws_mock = MagicMock()
        writer_mock.sheets = {"Test Anomalies": ws_mock}

        df_mock = MagicMock()
        mock_rename.return_value = df_mock

        result = generator._create_anomaly_sheet(writer_mock, "Test", pd.DataFrame())

        assert result == ws_mock, f"Expected {ws_mock}, got {result}"
        mock_header.assert_called_once_with(ws_mock)
        mock_numbers.assert_called_once_with(ws_mock)
        mock_cond.assert_called_once_with(ws_mock)
        mock_widths.assert_called_once_with(ws_mock)

def test_add_strategy_sheet(generator: ExcelReportGenerator) -> None:
    with patch('pandas.DataFrame.to_excel') as mock_to_excel, \
         patch('src.core.reporting.ExcelStyler.apply_header_style') as mock_header:

        writer_mock = MagicMock()
        ws_mock = MagicMock()
        writer_mock.sheets = {"Strategy": ws_mock}

        # Mocking the worksheet cell and column dimension logic
        ws_mock.column_dimensions = MagicMock()
        cell_mock = MagicMock()
        ws_mock.__getitem__.return_value = cell_mock

        generator._add_strategy_sheet(writer_mock, "test strategy")

        mock_header.assert_called_once_with(ws_mock)
        # Check if the column width was set
        assert ws_mock.column_dimensions['A'].width == 100, f"Expected 100 width, got {ws_mock.column_dimensions['A'].width}"
        # Check if alignment was set on A2
        assert cell_mock.alignment is not None, "Expected cell alignment to be set"
