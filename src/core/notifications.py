"""
Notification Service Implementations.
Provides decoupled alerting mechanisms.
"""
import json
import logging
from pathlib import Path
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.core.interfaces import NotificationService
from src.core.models import NotificationEvent

logger = logging.getLogger(__name__)


class FileNotificationService(NotificationService):
    """
    Logs notifications to a JSONL file.
    """
    def __init__(self, log_path: Path) -> None:
        self.log_path = log_path
        # Ensure directory exists
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.error(f"Failed to create notification log directory: {e}")

    def notify(self, event: NotificationEvent) -> None:
        """
        Appends the event to the log file in JSON format.
        """
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except OSError as e:
            # Fallback to system logger if file write fails
            logger.error(f"Failed to write to notification log: {e}")


class ConsoleNotificationService(NotificationService):
    """
    Displays notifications to the console using Rich.
    Designed to share a Console instance with the UI or create a new one.
    """
    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def notify(self, event: NotificationEvent) -> None:
        """
        Displays a styled notification panel.
        """
        style_map = {
            "INFO": "blue",
            "WARNING": "yellow",
            "ERROR": "bold red",
            "SUCCESS": "bold green"
        }
        style = style_map.get(event.level, "white")

        # Format: [Level] Title: Message
        content = Text()
        content.append(f"[{event.level}] ", style="bold")
        content.append(f"{event.title}\n", style="bold underline")
        content.append(event.message)

        # Only display panel for higher severity or specific configuration?
        # For now, display all as panels to differentiate from standard UI output.
        # Or maybe just print simplified text for INFO to avoid clutter.

        if event.level == "INFO":
            # Less intrusive for INFO
            self.console.print(f"[{style}]ℹ {event.title}: {event.message}[/{style}]")
        else:
            self.console.print(
                Panel(
                    content,
                    title=f"Notification: {event.timestamp.isoformat()}",
                    border_style=style,
                    expand=False
                )
            )


class CompositeNotificationService(NotificationService):
    """
    Delegates notifications to multiple services.
    """
    def __init__(self, services: List[NotificationService]) -> None:
        self.services = services

    def notify(self, event: NotificationEvent) -> None:
        """
        Broadcasts the event to all registered services.
        """
        for service in self.services:
            try:
                service.notify(event)
            except Exception as e:
                # robust error handling: one failure shouldn't stop others
                logger.error(f"Notification service {service} failed: {e}")
