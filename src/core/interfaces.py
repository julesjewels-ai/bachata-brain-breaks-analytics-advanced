"""
Interfaces for the core application.
Defines contracts for dependency injection to decouple implementation details.
"""
from typing import Protocol, Union, Optional, ContextManager, Any, List, AsyncGenerator, Dict
from io import BytesIO
import pandas as pd
from src.core.models import VideoAnalysisInput

class AIService(Protocol):
    """
    Protocol for AI operations.
    """
    def analyze_semantics(self, videos: List[VideoAnalysisInput]) -> str:
        """
        Analyzes video metadata to identify semantic patterns.
        """
        ...

    def analyze_stream(self, videos: List[VideoAnalysisInput]) -> AsyncGenerator[str, None]:
        """
        Stream analysis of video metadata.
        """
        ...

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

    async def display_stream(self, generator: AsyncGenerator[str, None]) -> None:
        """Displays a streaming response from an async generator."""
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

class ReportGenerator(Protocol):
    """
    Protocol for generating reports.
    """
    def generate_report(self, anomalies: Dict[str, pd.DataFrame], strategy: str, filepath: str) -> None:
        """
        Generates a report.
        """
        ...

class DataIngestionService(Protocol):
    """
    Protocol for data ingestion operations.
    """
    def ingest_data(self) -> pd.DataFrame:
        """
        Ingests channel data.

        Returns:
            pd.DataFrame: DataFrame containing video analysis data.
        """
        ...
