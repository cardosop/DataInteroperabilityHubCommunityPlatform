"""
Phase 83.6 — process_event_outbox management command tests.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.test import TestCase

# Patch where the command imports, not where the function is defined
_GET_PUB = "hub.apps.core.management.commands.process_event_outbox.get_outbox_publisher"


class ProcessEventOutboxCommandTest(TestCase):
    @patch(_GET_PUB)
    def test_once_processes_batch(self, mock_get):
        publisher = MagicMock()
        publisher.process_outbox.return_value = 5
        publisher.cleanup_old_events.return_value = 0
        mock_get.return_value = publisher
        out = StringIO()
        call_command("process_event_outbox", "--once", stdout=out)
        publisher.process_outbox.assert_called_once_with(batch_size=100)
        assert "5" in out.getvalue()

    @patch(_GET_PUB)
    def test_once_cleans_old_events(self, mock_get):
        publisher = MagicMock()
        publisher.process_outbox.return_value = 0
        publisher.cleanup_old_events.return_value = 10
        mock_get.return_value = publisher
        out = StringIO()
        call_command("process_event_outbox", "--once", "--cleanup-days=3", stdout=out)
        publisher.cleanup_old_events.assert_called_with(days=3)

    @patch(_GET_PUB)
    def test_empty_outbox_clean_exit(self, mock_get):
        publisher = MagicMock()
        publisher.process_outbox.return_value = 0
        publisher.cleanup_old_events.return_value = 0
        mock_get.return_value = publisher
        out = StringIO()
        call_command("process_event_outbox", "--once", stdout=out)
        assert "0" in out.getvalue()

    @patch(_GET_PUB)
    def test_custom_batch_size(self, mock_get):
        publisher = MagicMock()
        publisher.process_outbox.return_value = 0
        publisher.cleanup_old_events.return_value = 0
        mock_get.return_value = publisher
        call_command("process_event_outbox", "--once", "--batch-size=50")
        publisher.process_outbox.assert_called_once_with(batch_size=50)
