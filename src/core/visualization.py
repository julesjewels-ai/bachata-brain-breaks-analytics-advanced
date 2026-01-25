"""
Visualization module for generating static charts.
"""
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
from io import BytesIO
import pandas as pd
from src.core.interfaces import IVisualizer

class MatplotlibVisualizer:
    """Implementation of IVisualizer using Matplotlib."""

    def create_scatter_plot(self, df: pd.DataFrame, x_col: str, y_col: str, title: str) -> BytesIO:
        """
        Creates a scatter plot of two columns.
        """
        # Use Object-Oriented API for thread safety
        fig, ax = plt.subplots(figsize=(10, 6))

        # Plot data
        # Check if columns exist
        if x_col not in df.columns or y_col not in df.columns:
            plt.close(fig)
            raise ValueError(f"Columns {x_col} or {y_col} not found in DataFrame")

        ax.scatter(df[x_col], df[y_col], alpha=0.6, c='#4F81BD', edgecolors='w', s=80)

        ax.set_title(title)
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        ax.grid(True, linestyle='--', alpha=0.7)

        # Save to buffer
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        plt.close(fig)

        buf.seek(0)
        return buf
