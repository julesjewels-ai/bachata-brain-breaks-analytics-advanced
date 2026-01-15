import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_path_traversal_allowed_currently() -> None:
    """
    Demonstrates that the current implementation disallows directory separators,
    preventing path traversal or arbitrary file writes.
    """
    path = "tmp/report.xlsx"
    with pytest.raises(ValidationError) as excinfo:
        ReportConfig(filepath=path)
    assert "File path contains invalid characters" in str(excinfo.value)

def test_absolute_path_allowed_currently() -> None:
    path = "/tmp/report.xlsx"
    with pytest.raises(ValidationError) as excinfo:
        ReportConfig(filepath=path)
    assert "File path contains invalid characters" in str(excinfo.value)

def test_valid_filename() -> None:
    path = "bachata_analytics.xlsx"
    config = ReportConfig(filepath=path)
    assert config.filepath == path

def test_valid_filename_with_dots() -> None:
    path = "my.report.v1.xlsx"
    config = ReportConfig(filepath=path)
    assert config.filepath == path
