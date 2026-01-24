import io
import pandas as pd
import pytest
from src.core.visualization import MatplotlibVisualizer

def test_generate_heatmap_valid_data():
    viz = MatplotlibVisualizer()
    data = pd.DataFrame({
        'views': [100, 200, 300],
        'retention_avg_pct': [50.0, 60.0, 70.0]
    })

    img = viz.generate_heatmap(data, "Test Heatmap")

    assert isinstance(img, io.BytesIO)
    # Check for PNG magic bytes
    assert img.getvalue().startswith(b'\x89PNG')

def test_generate_heatmap_empty_data():
    viz = MatplotlibVisualizer()
    data = pd.DataFrame({'views': [], 'retention_avg_pct': []})

    img = viz.generate_heatmap(data, "Empty Heatmap")

    assert isinstance(img, io.BytesIO)
    assert img.getvalue().startswith(b'\x89PNG')

def test_generate_heatmap_missing_columns():
    viz = MatplotlibVisualizer()
    data = pd.DataFrame({'other': [1, 2]})

    img = viz.generate_heatmap(data, "Bad Data")

    assert isinstance(img, io.BytesIO)
