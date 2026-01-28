"""
Visualization module for generating static charts.
"""
from io import BytesIO
import matplotlib.pyplot as plt
import pandas as pd
from pydantic import BaseModel, Field

# Ensure headless backend for server/CLI environments
plt.switch_backend('Agg')

class VisualizationConfig(BaseModel):
    """Configuration for visualization generation."""
    title: str
    x_col: str
    y_col: str
    width: int = Field(10, description="Width in inches")
    height: int = Field(6, description="Height in inches")
    dpi: int = Field(100, description="DPI of the image")

class MatplotlibVisualizer:
    """Implementation of Visualizer using Matplotlib."""

    def generate_chart(self, df: pd.DataFrame, title: str, x_col: str, y_col: str) -> BytesIO:
        """
        Generates a scatter plot of x_col vs y_col.

        Args:
            df: The data.
            title: Chart title.
            x_col: X-axis column name.
            y_col: Y-axis column name.

        Returns:
            BytesIO: PNG image stream.
        """
        if df.empty:
             raise ValueError("DataFrame is empty, cannot generate chart.")

        # Validate columns exist
        if x_col not in df.columns or y_col not in df.columns:
             raise ValueError(f"Columns '{x_col}' or '{y_col}' not found in DataFrame columns: {df.columns.tolist()}")

        config = VisualizationConfig(title=title, x_col=x_col, y_col=y_col)  # type: ignore

        # Create figure
        fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

        # Plot data
        # Use a semantic color scheme if possible, otherwise default blue
        ax.scatter(df[x_col], df[y_col], alpha=0.7, c='#4F81BD', edgecolors='white', s=80)

        ax.set_title(config.title, fontsize=14, fontweight='bold')
        ax.set_xlabel(config.x_col, fontsize=12)
        ax.set_ylabel(config.y_col, fontsize=12)
        ax.grid(True, linestyle='--', alpha=0.5)

        # Save to buffer
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close(fig)
        buf.seek(0)

        return buf
