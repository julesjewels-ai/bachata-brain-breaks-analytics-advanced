"""
Tests for visualization module.
"""
import pandas as pd
from src.core.visualization import MatplotlibVisualizer


def test_generate_chart_success():
    df = pd.DataFrame({
        'x': [1, 2, 3],
        'y': [10, 20, 30]
    })
    viz = MatplotlibVisualizer()
    stream = viz.generate_chart(df, "Test Chart", "x", "y")
    assert stream is not None
    # Check magic number for PNG
    content = stream.getvalue()
    assert content.startswith(b'\x89PNG')


def test_generate_chart_empty_df():
    viz = MatplotlibVisualizer()
    import pytest
    with pytest.raises(ValueError, match="DataFrame is empty"):
        viz.generate_chart(pd.DataFrame(), "Title", "x", "y")


def test_generate_chart_missing_columns():
    viz = MatplotlibVisualizer()
    df = pd.DataFrame({'a': [1]})
    import pytest
    with pytest.raises(ValueError, match="Columns"):
        viz.generate_chart(df, "Title", "x", "y")
