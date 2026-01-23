import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_filepath_valid_simple():
    """Test valid filename without path separators."""
    config = ReportConfig(filepath="report.xlsx")
    assert config.filepath == "report.xlsx"

def test_filepath_valid_with_hyphen_underscore_space():
    """Test valid filename with allowed characters."""
    config = ReportConfig(filepath="my-report_v1 2.xlsx")
    assert config.filepath == "my-report_v1 2.xlsx"

def test_filepath_invalid_extension():
    """Test invalid extension."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="report.csv")
    assert "File must be an Excel (.xlsx) file" in str(exc.value)

def test_filepath_invalid_slash_separator():
    """Test rejection of directory separators (forward slash)."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="subdir/report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)

def test_filepath_invalid_backslash_separator():
    """Test rejection of directory separators (backslash)."""
    # Backslash is not in \w\-.
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="subdir\\report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)

def test_filepath_path_traversal():
    """Test path traversal detection (redundant check but good to verify)."""
    # The code checks ".." first.
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="../report.xlsx")
    assert "Path traversal detected" in str(exc.value)

def test_filepath_absolute_path():
    """Test rejection of absolute path."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="/tmp/report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)
