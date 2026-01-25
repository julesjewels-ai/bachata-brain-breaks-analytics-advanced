"""
Core interfaces for the Bachata Analytics application.
"""
from typing import Protocol
from io import BytesIO
import pandas as pd

class IVisualizer(Protocol):
    """Interface for generating visualizations."""

    def create_scatter_plot(self, df: pd.DataFrame, x_col: str, y_col: str, title: str) -> BytesIO:
        """
        Creates a scatter plot and returns the image as a byte stream.

        Args:
            df: DataFrame containing the data.
            x_col: Column name for X-axis.
            y_col: Column name for Y-axis.
            title: Title of the chart.

        Returns:
            BytesIO: Image data stream (e.g., PNG).
        """
        ...
