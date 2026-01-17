"""
Core interfaces for the application.
Defines contracts for external dependencies like UI, Data Persistence, etc.
"""
from typing import Protocol, ContextManager, Any
import pandas as pd

class IUserInterface(Protocol):
    """
    Protocol defining the contract for User Interface interactions.
    """
    def print_welcome(self, version: str = "1.0.0") -> None:
        ...

    def print_success(self, message: str) -> None:
        ...

    def print_error(self, message: str) -> None:
        ...

    def print_info(self, message: str) -> None:
        ...

    def print_step(self, message: str) -> None:
        ...

    def display_dataframe(self, df: pd.DataFrame, title: str) -> None:
        ...

    def display_agent_thought(self, thought: str) -> None:
        ...

    def show_spinner(self, description: str) -> ContextManager[Any]:
        ...
