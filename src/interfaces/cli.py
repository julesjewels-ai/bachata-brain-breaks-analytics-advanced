"""
CLI Interface module using Rich.
Handles all user interactions, input/output, and visual feedback.
"""
from typing import List, Optional, Callable, Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.theme import Theme
import pandas as pd
from contextlib import contextmanager

class RichConsole:
    """
    Handles rich console output for the application.
    Implements the Dependency Inversion Principle (DIP) by abstracting the UI details.
    """
    def __init__(self):
        self.theme = Theme({
            "info": "cyan",
            "warning": "yellow",
            "error": "bold red",
            "success": "bold green",
            "header": "bold blue",
            "title": "bold magenta"
        })
        self.console = Console(theme=self.theme)

    def print_welcome(self, version: str = "1.0.0") -> None:
        """Displays the application welcome banner."""
        self.console.print(
            Panel(
                f"[title]Bachata Brain Breaks Analytics[/title]\n[info]v{version}[/info]",
                subtitle="Audience & Retention Dashboard",
                border_style="blue"
            )
        )

    def print_success(self, message: str) -> None:
        """Prints a success message."""
        self.console.print(f"[success]✔ {message}[/success]")

    def print_error(self, message: str) -> None:
        """Prints an error message."""
        self.console.print(f"[error]✖ {message}[/error]")

    def print_info(self, message: str) -> None:
        """Prints an info message."""
        self.console.print(f"[info]ℹ {message}[/info]")

    def print_step(self, message: str) -> None:
        """Prints a step header."""
        self.console.print(f"\n[header]>> {message}[/header]")

    def display_dataframe(self, df: pd.DataFrame, title: str) -> None:
        """
        Displays a pandas DataFrame as a rich Table.
        """
        if df.empty:
            self.print_info(f"No data available for {title}.")
            return

        table = Table(title=title, show_header=True, header_style="bold magenta")

        # Add columns
        for column in df.columns:
            table.add_column(str(column))

        # Add rows
        for _, row in df.iterrows():
            # Convert all values to string for display
            row_data = [str(x) for x in row]
            table.add_row(*row_data)

        self.console.print(table)

    def display_agent_thought(self, thought: str) -> None:
        """Displays the agent's thought process in a panel."""
        self.console.print(
            Panel(
                thought,
                title="[bold purple]Gemini 3 Agent Analysis[/bold purple]",
                border_style="purple"
            )
        )

    @contextmanager
    def show_spinner(self, description: str) -> Any:
        """
        Context manager to show a spinner during a long-running task.
        """
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console,
            transient=True
        ) as progress:
            progress.add_task(description=description, total=None)
            yield
