"""
Notification services for Bachata Brain Breaks Analytics.
"""
import logging

from src.core.interfaces import NotificationService, UserInterface
from src.core.models import NotificationEvent

logger = logging.getLogger(__name__)


class ConsoleNotificationService(NotificationService):
    """
    Sends notifications to the console via UserInterface.
    """
    def __init__(self, ui: UserInterface):
        self.ui = ui

    def notify(self, event: NotificationEvent) -> None:
        """
        Displays notification on the console.
        """
        if event.level == 'error':
            self.ui.display_error(f"{event.title}: {event.message}")
        elif event.level == 'success':
            self.ui.display_success(f"{event.title}: {event.message}")
        elif event.level == 'warning':
            self.ui.display_status(f"WARNING: {event.title} - {event.message}")
        else:
            self.ui.display_info(f"{event.title}: {event.message}")


class FileNotificationService(NotificationService):
    """
    Logs notifications to a file (NDJSON format).
    """
    def __init__(self, filepath: str):
        self.filepath = filepath

    def notify(self, event: NotificationEvent) -> None:
        """
        Appends notification to a file.
        """
        try:
            with open(self.filepath, 'a') as f:
                f.write(event.model_dump_json() + '\n')
        except Exception as e:
            logger.error("Failed to log notification to file: %s", e)


class CompositeNotificationService(NotificationService):
    """
    Broadcasts notifications to multiple services.
    """
    def __init__(self, services: list[NotificationService]):
        self.services = services

    def notify(self, event: NotificationEvent) -> None:
        """
        Delegates notification to all registered services.
        """
        for service in self.services:
            try:
                service.notify(event)
            except Exception as e:
                logger.error("Notification service failed: %s", e)
