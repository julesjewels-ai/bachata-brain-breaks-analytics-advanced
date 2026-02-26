"""
Tests for Notification Services.
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, call, patch
from rich.console import Console
from src.core.notifications import (
    FileNotificationService, ConsoleNotificationService, CompositeNotificationService
)
from src.core.models import NotificationEvent

@pytest.fixture
def notification_event():
    return NotificationEvent(
        title="Test Event",
        message="This is a test message.",
        level="INFO"
    )

class TestFileNotificationService:
    def test_notify_writes_to_file(self, tmp_path, notification_event):
        log_file = tmp_path / "notifications.jsonl"
        service = FileNotificationService(log_file)

        service.notify(notification_event)

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        data = json.loads(content)
        assert data["title"] == "Test Event"
        assert data["message"] == "This is a test message."
        assert data["level"] == "INFO"

    def test_init_creates_directory(self, tmp_path):
        log_file = tmp_path / "subdir" / "notifications.jsonl"
        service = FileNotificationService(log_file)
        assert log_file.parent.exists()

class TestConsoleNotificationService:
    def test_notify_info_calls_print(self, notification_event):
        mock_console = Mock(spec=Console)
        service = ConsoleNotificationService(console=mock_console)

        service.notify(notification_event)

        mock_console.print.assert_called_once()
        # Verify call args contain message
        args, _ = mock_console.print.call_args
        assert "Test Event" in args[0]

    def test_notify_error_uses_panel(self):
        mock_console = Mock(spec=Console)
        service = ConsoleNotificationService(console=mock_console)
        event = NotificationEvent(
            title="Error Event",
            message="Something went wrong",
            level="ERROR"
        )

        service.notify(event)

        mock_console.print.assert_called_once()
        # Check if Panel was passed (it's hard to check exact Panel object, but we can check type)
        from rich.panel import Panel
        args, _ = mock_console.print.call_args
        assert isinstance(args[0], Panel)

class TestCompositeNotificationService:
    def test_notify_calls_all_services(self, notification_event):
        mock_service1 = Mock()
        mock_service2 = Mock()
        composite = CompositeNotificationService([mock_service1, mock_service2])

        composite.notify(notification_event)

        mock_service1.notify.assert_called_once_with(notification_event)
        mock_service2.notify.assert_called_once_with(notification_event)

    def test_notify_handles_exceptions(self, notification_event):
        mock_service1 = Mock()
        mock_service1.notify.side_effect = Exception("Fail")
        mock_service2 = Mock()
        composite = CompositeNotificationService([mock_service1, mock_service2])

        # Should not raise
        composite.notify(notification_event)

        mock_service1.notify.assert_called_once()
        mock_service2.notify.assert_called_once()
