"""
Interfaces for the core application.
Defines contracts for dependency injection to decouple implementation details.
"""
from typing import Protocol, Union, Optional, ContextManager, Any, List, Dict, AsyncGenerator
from io import BytesIO
import pandas as pd

class UserInterface(Protocol):
    """
    Protocol for user interaction.
    Allows swapping the console UI for a web UI or mock UI for testing.
    """
    def display_header(self, text: str) -> None:
        """Displays a major section header."""
        ...

    def display_section(self, text: str) -> None:
        """Displays a subsection header."""
        ...

    def display_status(self, text: str) -> None:
        """Displays a status update or progress message."""
        ...

    def display_table(self, data: pd.DataFrame, title: Optional[str] = None) -> None:
        """Displays structured data as a table."""
        ...

    def display_error(self, error: Union[Exception, str]) -> None:
        """Displays an error message."""
        ...

    def display_success(self, text: str) -> None:
        """Displays a success message."""
        ...

    def display_info(self, text: str) -> None:
        """Displays a general informational message."""
        ...

    def display_message(self, text: str) -> None:
        """Displays a standard message."""
        ...

    def loading(self, text: str) -> ContextManager[Any]:
        """Returns a context manager for a loading state."""
        ...


class Visualizer(Protocol):
    """
    Protocol for generating static visualizations.
    """
    def generate_chart(self, df: pd.DataFrame, title: str, x_col: str, y_col: str) -> BytesIO:
        """
        Generates a chart and returns the image as a byte stream.

        Args:
            df: DataFrame containing the data.
            title: Title of the chart.
            x_col: Column name for X-axis.
            y_col: Column name for Y-axis.

        Returns:
            BytesIO: Image data stream (e.g., PNG).
        """
        ...


class AIService(Protocol):
    """
    Protocol for AI operations.
    Supports both synchronous and streaming analysis.
    """
    def analyze_semantics(self, videos: List[Dict[str, Any]]) -> str:
        """
        Analyzes video data semantics and returns a complete strategy string.
        """
        ...

    def analyze_stream(self, videos: List[Dict[str, Any]]) -> AsyncGenerator[str, None]:
        """
        Analyzes video data and yields tokens as they are generated.
        Note: Implemented as an async generator.
        """
        ...
