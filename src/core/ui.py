"""
User Interface implementation using the Rich library.
"""
from typing import ContextManager
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

class RichConsoleUI:
    """
    Implementation of UserInterface using Rich.
    Provides structured and styled output for the CLI.
    """
    def __init__(self) -> None:
        self.console = Console()

    def display_header(self, title: str) -> None:
        """Displays a styled header using a Panel."""
        self.console.print(Panel(Text(title, justify="center", style="bold white"), style="blue"))

    def display_status(self, message: str) -> ContextManager:
        """Displays a spinner status for long-running tasks."""
        return self.console.status(message, spinner="dots")

    def display_dataframe(self, df: pd.DataFrame, title: str) -> None:
        """Displays a pandas DataFrame as a Rich Table."""
        if df.empty:
            self.console.print(f"[yellow]No data available for {title}[/yellow]")
            return

        # Pre-process for display (renaming, formatting)
        # We work on a copy to avoid modifying the original dataframe
        display_df = df.copy()

        # Apply standard formatting logic (mirrors formatting.py but for rich table)
        if 'views' in display_df.columns:
            display_df['views'] = display_df['views'].apply(lambda x: f"{x:,.0f}")
        if 'retention_avg_pct' in display_df.columns:
            display_df['retention_avg_pct'] = display_df['retention_avg_pct'].apply(lambda x: f"{x:.1f}%")

        # Rename columns to human-readable format
        column_mapping = {
            'title': 'Video Title',
            'views': 'Views',
            'retention_avg_pct': 'Retention',
            'video_id': 'ID',
            'type': 'Type',
            'publish_date': 'Date'
        }
        # Only rename columns that exist
        display_df = display_df.rename(columns={k: v for k, v in column_mapping.items() if k in display_df.columns})

        table = Table(title=title, show_header=True, header_style="bold magenta")

        for column in display_df.columns:
            # Right align numeric columns
            if column in ["Views", "Retention"]:
                table.add_column(str(column), justify="right", style="green")
            else:
                table.add_column(str(column), justify="left", style="cyan")

        for _, row in display_df.iterrows():
            table.add_row(*[str(x) for x in row])

        self.console.print(table)
        self.console.print() # Add empty line

    def display_message(self, message: str, style: str = "info") -> None:
        """Displays a message with optional styling."""
        if style == "info":
            self.console.print(message)
        elif style == "success":
            self.console.print(f"[green]✔ {message}[/green]")
        elif style == "warning":
            self.console.print(f"[yellow]⚠ {message}[/yellow]")
        else:
            self.console.print(message)

    def display_error(self, message: str) -> None:
        """Displays an error message."""
        self.console.print(f"[bold red]✘ Error:[/bold red] {message}")
