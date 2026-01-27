import pytest
from pydantic import ValidationError
from src.core.reporting import ReportConfig

def test_path_traversal_blocked():
    """Test that path traversal attempts are blocked."""
    invalid_paths = [
        "../report.xlsx",
        "/tmp/report.xlsx",
        "report/data.xlsx",
        "\\report.xlsx",
        "nested/report.xlsx"
    ]

    for path in invalid_paths:
        with pytest.raises(ValidationError) as exc:
            ReportConfig(filepath=path)
        assert "File path contains invalid characters" in str(exc.value) or "Path traversal detected" in str(exc.value)

def test_valid_filename():
    """Test that valid filenames are allowed."""
    valid_paths = [
        "report.xlsx",
        "my-report.xlsx",
        "report 2023.xlsx",
        "final_report.xlsx"
    ]

    for path in valid_paths:
        config = ReportConfig(filepath=path)
        assert config.filepath == path
