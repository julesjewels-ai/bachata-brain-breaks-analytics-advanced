import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_report_config_valid_filename():
    """Test that a valid filename is accepted."""
    config = ReportConfig(filepath="report.xlsx")
    assert config.filepath == "report.xlsx"

def test_report_config_path_traversal_dots():
    """Test that '..' is rejected."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="../report.xlsx")
    assert "Path traversal detected" in str(exc.value)

def test_report_config_directory_separator():
    """Test that directory separators are rejected (to restrict to current dir)."""
    # This currently passes in the code (vulnerable), so we expect it to fail
    # if we were asserting the fix already.
    # But since I want to confirm the fix works later, I will assert that it raises ValidationError.

    # Testing forward slash
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="subdir/report.xlsx")
    assert "File path contains invalid characters" in str(exc.value)

def test_report_config_invalid_extension():
    """Test that non-xlsx extensions are rejected."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="report.csv")
    assert "File must be an Excel (.xlsx) file" in str(exc.value)

def test_report_config_special_chars():
    """Test that special characters are rejected."""
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath="report$$.xlsx")
    assert "File path contains invalid characters" in str(exc.value)
