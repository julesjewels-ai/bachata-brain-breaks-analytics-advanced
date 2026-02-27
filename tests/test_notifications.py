"""
Tests for notification services.
"""
import json
import os
from unittest.mock import Mock
from src.core.notifications import (
    ConsoleNotificationService, FileNotificationService,
    CompositeNotificationService
)
from src.core.models import NotificationEvent
from src.core.interfaces import UserInterface


class TestConsoleNotificationService:
    def test_notify_info(self):
        ui = Mock(spec=UserInterface)
        service = ConsoleNotificationService(ui)
        event = NotificationEvent(
            title="Info", message="Info Message", level='info'
        )

        service.notify(event)

        ui.display_info.assert_called_with("Info: Info Message")

    def test_notify_warning(self):
        ui = Mock(spec=UserInterface)
        service = ConsoleNotificationService(ui)
        event = NotificationEvent(
            title="Warning", message="Warning Message", level='warning'
        )

        service.notify(event)

        ui.display_status.assert_called_with(
            "WARNING: Warning - Warning Message"
        )

    def test_notify_error(self):
        ui = Mock(spec=UserInterface)
        service = ConsoleNotificationService(ui)
        event = NotificationEvent(
            title="Error", message="Error Message", level='error'
        )

        service.notify(event)

        ui.display_error.assert_called_with("Error: Error Message")

    def test_notify_success(self):
        ui = Mock(spec=UserInterface)
        service = ConsoleNotificationService(ui)
        event = NotificationEvent(
            title="Success", message="Success Message", level='success'
        )

        service.notify(event)

        ui.display_success.assert_called_with("Success: Success Message")


class TestFileNotificationService:
    def test_notify_writes_to_file(self, tmp_path):
        filepath = tmp_path / "notifications.jsonl"
        service = FileNotificationService(str(filepath))
        event = NotificationEvent(
            title="Test", message="Test Message", level='info'
        )

        service.notify(event)

        assert os.path.exists(filepath)
        with open(filepath, 'r') as f:
            line = f.readline()
            data = json.loads(line)
            assert data['title'] == "Test"
            assert data['message'] == "Test Message"
            assert data['level'] == "info"
            assert 'timestamp' in data


class TestCompositeNotificationService:
    def test_notify_delegates_to_services(self):
        service1 = Mock()
        service2 = Mock()
        composite = CompositeNotificationService([service1, service2])
        event = NotificationEvent(
            title="Test", message="Test Message", level='info'
        )

        composite.notify(event)

        service1.notify.assert_called_with(event)
        service2.notify.assert_called_with(event)

    def test_notify_handles_service_failure(self):
        service1 = Mock(side_effect=Exception("Fail"))
        service2 = Mock()
        composite = CompositeNotificationService([service1, service2])
        event = NotificationEvent(
            title="Test", message="Test Message", level='info'
        )

        # Should not raise exception
        composite.notify(event)

        service1.notify.assert_called_with(event)
        service2.notify.assert_called_with(event)
