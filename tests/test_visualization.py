"""
Tests for the visualization module.
"""
import pytest
import pandas as pd
from io import BytesIO
from src.core.visualization import MatplotlibVisualizer

def test_create_scatter_plot():
    """Test that create_scatter_plot returns a valid BytesIO object."""
    viz = MatplotlibVisualizer()
    df = pd.DataFrame({
        'x': [1, 2, 3],
        'y': [4, 5, 6]
    })

    stream = viz.create_scatter_plot(df, 'x', 'y', 'Test Plot')

    assert isinstance(stream, BytesIO)
    content = stream.getvalue()
    # Check for PNG magic numbers
    assert content.startswith(b'\x89PNG')

def test_create_scatter_plot_missing_columns():
    """Test that missing columns raise ValueError."""
    viz = MatplotlibVisualizer()
    df = pd.DataFrame({'a': [1]})

    with pytest.raises(ValueError):
        viz.create_scatter_plot(df, 'x', 'y', 'Test')
