"""
Notification services for Bachata Brain Breaks Analytics.
Implements various strategies for dispatching notifications.
"""
import logging
from typing import List
from pathlib import Path

from src.core.interfaces import NotificationService
from src.core.models import NotificationEvent

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Base exception for notification errors."""
    pass


class ConsoleNotificationService(NotificationService):
    """
    Sends notifications to the console.
    Designed to be lightweight and not interfere with the main UI if possible,
    or used as a debug output.
    """
    def send(self, event: NotificationEvent) -> None:
        """
        Prints the notification to the console.
        """
        # Mapping level to simple indicators
        indicators = {
            'INFO': 'ℹ',
            'WARNING': '⚠',
            'ERROR': '✖',
            'SUCCESS': '✔'
        }
        icon = indicators.get(event.level, '•')
        timestamp = event.timestamp.strftime("%H:%M:%S")

        # We use standard print here or logging to avoid conflicting with
        # RichConsoleUI if both are writing to stdout. Ideally this might use
        # a separate channel or be integrated into the UI. For now, we'll use
        # logging which is safe.
        log_msg = f"[{timestamp}] {icon} {event.title}: {event.message}"

        if event.level == 'ERROR':
            logger.error(log_msg)
        elif event.level == 'WARNING':
            logger.warning(log_msg)
        else:
            logger.info(log_msg)


class FileNotificationService(NotificationService):
    """
    Appends notifications to a JSONL file for audit trails.
    """
    def __init__(self, log_path: str) -> None:
        self.log_path = Path(log_path)
        try:
            # Ensure directory exists
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise NotificationError(
                f"Failed to create notification log directory: {e}"
            ) from e

    def send(self, event: NotificationEvent) -> None:
        """
        Appends the event to the log file.
        """
        try:
            with self.log_path.open("a", encoding="utf-8") as f:
                # Serialize using model_dump, handling datetime automatically
                # if using pydantic v2 or custom encoder. Pydantic's
                # model_dump_json handles it.
                f.write(event.model_dump_json() + "\n")
        except OSError as e:
            # We log the error but don't raise to prevent crashing the main app
            logger.error(f"Failed to write notification to file: {e}")


class CompositeNotificationService(NotificationService):
    """
    Broadcasts notifications to multiple services.
    """
    def __init__(self, services: List[NotificationService]) -> None:
        self.services = services

    def send(self, event: NotificationEvent) -> None:
        """
        Sends the event to all registered services.
        """
        for service in self.services:
            try:
                service.send(event)
            except Exception as e:
                # Catch-all to ensure one failure doesn't stop others
                logger.error(f"Notification service {service} failed: {e}")
