import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_filepath_valid():
    """Test valid filepath (filename only)."""
    config = ReportConfig(filepath="report.xlsx")
    assert config.filepath == "report.xlsx"

def test_filepath_valid_with_spaces_and_hyphens():
    """Test valid filepath with spaces and hyphens."""
    config = ReportConfig(filepath="my-report 2024.xlsx")
    assert config.filepath == "my-report 2024.xlsx"

def test_filepath_invalid_extension():
    """Test invalid extension."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="report.txt")
    assert "File must be an Excel (.xlsx) file" in str(exc.value)

def test_filepath_path_traversal_dots():
    """Test path traversal with dots."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="../report.xlsx")
    assert "Path traversal detected" in str(exc.value)

def test_filepath_directory_separator():
    """Test that directory separators are rejected (Strict Filename Only)."""
    # This currently passes validation (no error raised) in the code, so this test will fail before the fix.
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="reports/report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)

def test_filepath_absolute_path():
    """Test that absolute paths are rejected."""
    # This currently passes validation before the fix.
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="/tmp/report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)
