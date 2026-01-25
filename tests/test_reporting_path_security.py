import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_filepath_valid_filename():
    """Test valid filename without directory traversal."""
    config = ReportConfig(filepath="report.xlsx")
    assert config.filepath == "report.xlsx"

def test_filepath_valid_filename_with_spaces():
    """Test valid filename with spaces and hyphens."""
    config = ReportConfig(filepath="my-report 2024.xlsx")
    assert config.filepath == "my-report 2024.xlsx"

def test_filepath_directory_traversal_parent():
    """Test detection of parent directory traversal."""
    with pytest.raises(ValueError, match="Path traversal detected"):
        ReportConfig(filepath="../report.xlsx")

def test_filepath_directory_traversal_slash():
    """
    Test detection of directory separators (slash).
    This ensures files can only be saved in the current directory.
    """
    with pytest.raises(ValueError, match="File path contains invalid characters"):
        ReportConfig(filepath="subdir/report.xlsx")

def test_filepath_directory_traversal_absolute():
    """Test detection of absolute paths."""
    with pytest.raises(ValueError, match="File path contains invalid characters"):
        ReportConfig(filepath="/tmp/report.xlsx")

def test_filepath_invalid_extension():
    """Test valid extension check."""
    with pytest.raises(ValueError, match="File must be an Excel"):
        ReportConfig(filepath="report.txt")
