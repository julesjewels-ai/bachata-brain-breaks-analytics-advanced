"""
Tests for notification services.
"""
import pytest
import json
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from src.core.notifications import (
    ConsoleNotificationService,
    FileNotificationService,
    CompositeNotificationService,
    NotificationError
)
from src.core.models import NotificationEvent


@pytest.fixture
def sample_event():
    return NotificationEvent(
        title="Test Event",
        message="This is a test notification.",
        level="INFO",
        timestamp=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    )


class TestConsoleNotificationService:
    def test_send_info(self, sample_event):
        service = ConsoleNotificationService()
        with patch("src.core.notifications.logger") as mock_logger:
            service.send(sample_event)
            mock_logger.info.assert_called_once()
            args, _ = mock_logger.info.call_args
            assert "Test Event" in args[0]
            assert "ℹ" in args[0]

    def test_send_error(self, sample_event):
        service = ConsoleNotificationService()
        sample_event.level = "ERROR"
        with patch("src.core.notifications.logger") as mock_logger:
            service.send(sample_event)
            mock_logger.error.assert_called_once()
            args, _ = mock_logger.error.call_args
            assert "✖" in args[0]


class TestFileNotificationService:
    def test_init_creates_directory(self, tmp_path):
        log_file = tmp_path / "logs" / "notifications.jsonl"
        FileNotificationService(str(log_file))
        assert log_file.parent.exists()

    def test_send_writes_json(self, tmp_path, sample_event):
        log_file = tmp_path / "notifications.jsonl"
        service = FileNotificationService(str(log_file))

        service.send(sample_event)

        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        data = json.loads(content)

        assert data["title"] == sample_event.title
        assert data["message"] == sample_event.message
        assert data["level"] == sample_event.level
        # Pydantic v2 usually serializes datetime to ISO string
        assert "timestamp" in data

    def test_init_error(self):
        with patch(
            "pathlib.Path.mkdir", side_effect=OSError("Permission denied")
        ):
            with pytest.raises(NotificationError):
                FileNotificationService("/invalid/path/logs.jsonl")

    def test_send_error_handling(self, tmp_path, sample_event):
        log_file = tmp_path / "notifications.jsonl"
        service = FileNotificationService(str(log_file))

        # Simulate file write error (e.g. read-only)
        # Mocking open on the path instance is tricky, easier to mock open
        # builtin but pathlib uses io.open or internal calls.
        # Let's mock the open method of Path object if possible or just the
        # call

        with patch("pathlib.Path.open", side_effect=OSError("Disk full")):
            with patch("src.core.notifications.logger") as mock_logger:
                service.send(sample_event)
                mock_logger.error.assert_called_once()
                assert "Failed to write notification" in (
                    mock_logger.error.call_args[0][0]
                )


class TestCompositeNotificationService:
    def test_send_broadcasts(self, sample_event):
        mock_service_1 = Mock()
        mock_service_2 = Mock()
        composite = CompositeNotificationService(
            [mock_service_1, mock_service_2]
        )

        composite.send(sample_event)

        mock_service_1.send.assert_called_once_with(sample_event)
        mock_service_2.send.assert_called_once_with(sample_event)

    def test_send_isolation(self, sample_event):
        # Service 1 fails, Service 2 should still run
        mock_service_1 = Mock()
        mock_service_1.send.side_effect = Exception("Boom")
        mock_service_2 = Mock()

        composite = CompositeNotificationService(
            [mock_service_1, mock_service_2]
        )

        with patch("src.core.notifications.logger") as mock_logger:
            composite.send(sample_event)

            mock_service_1.send.assert_called_once()
            mock_service_2.send.assert_called_once()
            mock_logger.error.assert_called_once()
