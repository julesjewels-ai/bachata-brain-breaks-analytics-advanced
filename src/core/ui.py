"""
User Interface implementation using Rich.
"""
from typing import Union, Optional, ContextManager, Any, AsyncGenerator
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich import box

from src.core.interfaces import UserInterface

class RichConsoleUI(UserInterface):
    """
    Implementation of UserInterface using the Rich library.
    """
    def __init__(self, console: Optional[Console] = None) -> None:
        """
        Initialize the RichConsoleUI.

        Args:
            console: Optional Rich Console instance. If None, a new Console is created.
                     Useful for testing or overriding default console behavior.
        """
        self.console = console or Console()

    def display_header(self, text: str) -> None:
        self.console.print(Panel(Text(text, justify="center", style="bold white"), style="bold blue"))

    def display_section(self, text: str) -> None:
        self.console.print(f"\n[bold cyan]--- {text} ---[/bold cyan]")

    def display_status(self, text: str) -> None:
        self.console.print(f"[yellow]{text}[/yellow]")

    def display_table(self, data: pd.DataFrame, title: Optional[str] = None) -> None:
        if data.empty:
            self.console.print("[italic dim]No data available.[/italic dim]")
            return

        table = Table(title=title, box=box.ROUNDED)

        for col_name in data.columns:
            justify: Any = "left"
            style = "cyan"

            # specific columns should be right aligned and green
            # We check specific names or numeric types
            if pd.api.types.is_numeric_dtype(data[col_name]) or col_name in ["Views", "Retention", "Retention (%)"]:
                justify = "right"
                style = "green"

            table.add_column(str(col_name), justify=justify, style=style)

        for _, row in data.iterrows():
            # Convert row values to strings for display
            rendered_row = []
            for val in row:
                # If it's a float and looks like a percentage (small number?) or huge number?
                # Actually, let's rely on the caller to format values if specific formatting (like %) is needed.
                # Or we can do simple formatting here.
                # Let's just stringify for now to be safe and generic.
                rendered_row.append(str(val))
            table.add_row(*rendered_row)

        self.console.print(table)

    def display_error(self, error: Union[Exception, str]) -> None:
        self.console.print(f"[bold red]Error:[/bold red] {error}")

    def display_success(self, text: str) -> None:
        self.console.print(f"[bold green]✔ {text}[/bold green]")

    def display_info(self, text: str) -> None:
        self.console.print(f"[blue]ℹ {text}[/blue]")

    def display_message(self, text: str) -> None:
        self.console.print(text)

    def loading(self, text: str) -> ContextManager[Any]:
        return self.console.status(text, spinner="dots")

    async def display_stream(self, generator: AsyncGenerator[str, None]) -> None:
        text_buffer = Text()
        # Use Live to update the text in place as chunks arrive
        with Live(text_buffer, console=self.console, refresh_per_second=10) as live:
            async for chunk in generator:
                text_buffer.append(chunk)
                live.update(text_buffer)
        self.console.print()  # Ensure final newline
