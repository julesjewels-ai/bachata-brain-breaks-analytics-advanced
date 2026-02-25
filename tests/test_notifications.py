import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.core.notifications import (
    ConsoleNotificationService, FileNotificationService, CompositeNotificationService
)

def test_file_notification_service():
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        filepath = tmp.name

    try:
        service = FileNotificationService(filepath=filepath)
        service.notify("Test", "Message", "INFO")

        with open(filepath, "r") as f:
            line = f.readline()
            data = json.loads(line)

        assert data["title"] == "Test"
        assert data["message"] == "Message"
        assert data["level"] == "INFO"
        assert "timestamp" in data
    finally:
        Path(filepath).unlink(missing_ok=True)

def test_console_notification_service(caplog):
    service = ConsoleNotificationService()
    with caplog.at_level("INFO"):
        service.notify("Test", "Console Message", "INFO")
        assert "[Test] Console Message" in caplog.text

def test_composite_notification_service():
    mock_service1 = MagicMock()
    mock_service2 = MagicMock()

    service = CompositeNotificationService([mock_service1, mock_service2])
    service.notify("Title", "Body", "WARNING")

    mock_service1.notify.assert_called_once_with("Title", "Body", "WARNING")
    mock_service2.notify.assert_called_once_with("Title", "Body", "WARNING")

def test_composite_notification_service_resilience():
    # Ensure failure in one service doesn't stop others
    failing_service = MagicMock()
    failing_service.notify.side_effect = Exception("Boom")
    working_service = MagicMock()

    service = CompositeNotificationService([failing_service, working_service])
    service.notify("Title", "Body", "INFO")

    working_service.notify.assert_called_once()
