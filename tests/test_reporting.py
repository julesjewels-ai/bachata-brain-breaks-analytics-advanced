"""
Tests for the reporting module.
"""
import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from src.core.reporting import ExcelReportGenerator

@pytest.fixture
def mock_anomalies():
    return {
        'Viral': pd.DataFrame({
            'video_id': ['1'],
            'title': ['Test Video'],
            'views': [1000],
            'retention_avg_pct': [90.0],
            'type': ['Shorts'],
            'publish_date': ['2023-01-01']
        })
    }

def test_generate_excel_with_logo(mock_anomalies, tmp_path):
    """Test that generate_excel attempts to embed a logo if provided."""
    filepath = tmp_path / "test_report.xlsx"
    generator = ExcelReportGenerator()

    # Mock ImageEmbedder to verify interactions without real image file
    with patch("src.core.reporting.ImageEmbedder") as MockEmbedder:
        mock_instance = MockEmbedder.return_value

        generator.generate_excel(
            anomalies=mock_anomalies,
            strategy="Analysis",
            filepath=str(filepath),
            logo_path="logo.png"
        )

        # Verify ImageEmbedder was initialized
        assert MockEmbedder.called

        # Verify add_image was called
        # Anchor should be at column C (3) + 2 = E (5). "E1"
        args = mock_instance.add_image.call_args
        assert args is not None
        assert args.kwargs['image_path'] == "logo.png"
        assert args.kwargs['anchor'].endswith('1') # Should be row 1
