"""
Visualization service using Matplotlib.
Implements the IVisualizer interface to generate charts/images.
"""
import matplotlib
# Set backend to Agg to avoid GUI requirement
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import pandas as pd
from src.core.interfaces import IVisualizer

class MatplotlibVisualizer:
    """
    Concrete implementation of IVisualizer using Matplotlib.
    """
    def generate_heatmap(self, data: pd.DataFrame, title: str) -> io.BytesIO:
        """
        Generates a scatter plot (heatmap style) of Views vs Retention.
        """
        # Create a new figure to avoid thread safety issues with global state
        fig, ax = plt.subplots(figsize=(10, 6))

        # Check if required columns exist
        if 'views' not in data.columns or 'retention_avg_pct' not in data.columns:
            # Create an empty plot with a warning if data is missing columns
            ax.text(0.5, 0.5, 'Missing Data for Visualization',
                    horizontalalignment='center', verticalalignment='center')
        elif data.empty:
             ax.text(0.5, 0.5, 'No Data Available',
                    horizontalalignment='center', verticalalignment='center')
        else:
            # Scatter plot with color mapping for retention
            sc = ax.scatter(
                data['views'],
                data['retention_avg_pct'],
                c=data['retention_avg_pct'],
                cmap='viridis',
                s=100,
                alpha=0.7,
                edgecolors='w'
            )
            fig.colorbar(sc, ax=ax, label='Retention (%)')

            ax.set_title(title)
            ax.set_xlabel('Views')
            ax.set_ylabel('Retention (%)')
            ax.grid(True, linestyle='--', alpha=0.5)

        # Save to buffer
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close(fig)
        buf.seek(0)

        return buf
