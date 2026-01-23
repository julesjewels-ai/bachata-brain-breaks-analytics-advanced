"""
Interfaces for the core application components.
Defines contracts for user interaction to enable Dependency Inversion.
"""
from typing import Protocol, ContextManager
import pandas as pd

class UserInterface(Protocol):
    """
    Abstract interface for user interactions.
    Adheres to the Dependency Inversion Principle.
    """

    def display_header(self, title: str) -> None:
        """Displays a styled header."""
        ...

    def display_status(self, message: str) -> ContextManager:
        """Displays a status indicator (e.g., spinner) for long-running tasks."""
        ...

    def display_dataframe(self, df: pd.DataFrame, title: str) -> None:
        """Displays a pandas DataFrame in a formatted table."""
        ...

    def display_message(self, message: str, style: str = "info") -> None:
        """Displays a generic message with optional styling."""
        ...

    def display_error(self, message: str) -> None:
        """Displays an error message."""
        ...
