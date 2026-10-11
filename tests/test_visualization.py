"""
Tests for visualization module.
"""
from io import BytesIO

import pandas as pd
import pytest

from src.core.visualization import MatplotlibVisualizer


def test_generate_chart_success():
    """Test valid chart generation."""
    data = {
        'views': [100, 200, 300, 500, 1000],
        'retention': [10.5, 20.5, 30.5, 45.0, 60.0]
    }
    df = pd.DataFrame(data)

    viz = MatplotlibVisualizer()
    stream = viz.generate_chart(df, "Test Chart", "retention", "views")

    assert isinstance(stream, BytesIO)
    # Check that some data was written
    assert stream.getbuffer().nbytes > 100

def test_generate_chart_missing_columns():
    """Test error when columns missing."""
    data = {'views': [1]}
    df = pd.DataFrame(data)
    viz = MatplotlibVisualizer()

    with pytest.raises(ValueError, match="Columns"):
        viz.generate_chart(df, "Title", "missing", "views")

def test_generate_chart_empty_df():
    """Test error when DF is empty."""
    df = pd.DataFrame()
    viz = MatplotlibVisualizer()

    with pytest.raises(ValueError, match="empty"):
        viz.generate_chart(df, "Title", "x", "y")
