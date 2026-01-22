import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_report_config_path_traversal_slash_rejection():
    """
    Test that ReportConfig rejects paths with directory separators.
    This enforces the security boundary that files must be saved in the current directory only.
    """
    # This input contains a slash, which currently MIGHT be allowed by the loose regex.
    # We want to ensure it is REJECTED.
    invalid_path = "folder/report.xlsx"

    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath=invalid_path)

    # Check that it's the regex validation error
    assert "File path contains invalid characters" in str(exc.value)

def test_report_config_valid_filename():
    """Test that a simple filename is accepted."""
    valid_path = "report.xlsx"
    config = ReportConfig(filepath=valid_path)
    assert config.filepath == valid_path

def test_report_config_path_traversal_dots():
    """Test that .. is rejected (existing check)."""
    invalid_path = "../report.xlsx"
    with pytest.raises(ValidationError) as exc:
        ReportConfig(filepath=invalid_path)
    assert "Path traversal detected" in str(exc.value)
