"""
Notification service implementations.
Provides decoupled notification mechanisms.
"""
import logging
from typing import List, Literal
from pathlib import Path

from src.core.interfaces import NotificationService
from src.core.models import NotificationEvent

logger = logging.getLogger(__name__)


class ConsoleNotificationService(NotificationService):
    """
    Writes notifications to the console via standard logging.
    Distinct from the User Interface, primarily for operator logs.
    """
    def notify(
        self,
        title: str,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "SUCCESS"] = "INFO"
    ) -> None:
        formatted_msg = f"[{title}] {message}"
        if level == "ERROR":
            logger.error(formatted_msg)
        elif level == "WARNING":
            logger.warning(formatted_msg)
        else:
            logger.info(formatted_msg)


class FileNotificationService(NotificationService):
    """
    Appends notifications to a JSONL file for audit purposes.
    """
    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        # Ensure directory exists
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def notify(
        self,
        title: str,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "SUCCESS"] = "INFO"
    ) -> None:
        event = NotificationEvent(
            title=title,
            message=message,
            level=level
        )
        try:
            with open(self.filepath, "a", encoding="utf-8") as f:
                f.write(event.model_dump_json() + "\n")
        except IOError as e:
            # Fallback to logger if file write fails
            logger.error(f"Failed to write notification to file: {e}")


class CompositeNotificationService(NotificationService):
    """
    Broadcasts notifications to multiple services.
    """
    def __init__(self, services: List[NotificationService]):
        self.services = services

    def notify(
        self,
        title: str,
        message: str,
        level: Literal["INFO", "WARNING", "ERROR", "SUCCESS"] = "INFO"
    ) -> None:
        for service in self.services:
            try:
                service.notify(title, message, level)
            except Exception as e:
                logger.error(f"Notification service failed: {e}")
