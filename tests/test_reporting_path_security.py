import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_filepath_directory_traversal_with_slash():
    """Test that file paths cannot contain directory separators."""
    with pytest.raises(ValidationError, match="invalid characters"):
        ReportConfig(filepath="subdir/report.xlsx")

def test_filepath_absolute_path():
    """Test that file paths cannot be absolute."""
    with pytest.raises(ValidationError, match="invalid characters"):
        ReportConfig(filepath="/tmp/report.xlsx")

def test_valid_filename():
    """Test that a simple filename is valid."""
    config = ReportConfig(filepath="report.xlsx")
    assert config.filepath == "report.xlsx"

def test_valid_filename_with_spaces():
    """Test that a filename with spaces is valid."""
    config = ReportConfig(filepath="My Report.xlsx")
    assert config.filepath == "My Report.xlsx"
