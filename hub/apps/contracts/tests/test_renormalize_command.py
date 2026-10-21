"""
Phase 83.1 — renormalize_contracts management command tests.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class RenormalizeContractsCommandTest(TestCase):
    @patch("hub.apps.contracts.tasks.renormalize_contracts_v310")
    def test_sync_processes_contracts(self, mock_task):
        mock_task.return_value = {"processed": 5, "failed": 0}
        out = StringIO()
        call_command("renormalize_contracts", "--spec-version=3.1.0", "--sync", stdout=out)
        mock_task.assert_called_once()
        assert "5" in out.getvalue()

    @patch("hub.apps.contracts.tasks.renormalize_contracts_v310")
    def test_dry_run_shows_count(self, mock_task):
        mock_task.return_value = {"processed": 3, "failed": 0, "dry_run_warnings": {}}
        out = StringIO()
        call_command("renormalize_contracts", "--spec-version=3.1.0", "--dry-run", stdout=out)
        assert "dry-run" in out.getvalue().lower() or "3" in out.getvalue()

    def test_invalid_version_exits_with_error(self):
        err = StringIO()
        call_command("renormalize_contracts", "--spec-version=2.0.0", stderr=err)
        assert "3.1.0" in err.getvalue()

    @patch("hub.apps.contracts.tasks.renormalize_contracts_v310")
    def test_batch_size_passed_through(self, mock_task):
        mock_task.return_value = {"processed": 0, "failed": 0}
        call_command("renormalize_contracts", "--spec-version=3.1.0", "--sync", "--batch-size=50")
        assert mock_task.call_args[1]["batch_size"] == 50

    @patch("hub.apps.contracts.tasks.renormalize_contracts_v310")
    def test_tenant_id_passed_through(self, mock_task):
        mock_task.return_value = {"processed": 0, "failed": 0}
        call_command("renormalize_contracts", "--spec-version=3.1.0", "--sync", "--tenant-id=abc")
        assert mock_task.call_args[1]["tenant_id"] == "abc"

    @patch("django_rq.get_queue")
    @patch("hub.apps.contracts.tasks.renormalize_contracts_v310")
    def test_enqueue_mode(self, mock_task, mock_queue):
        mock_q = MagicMock()
        mock_q.enqueue.return_value = MagicMock(id="rq-123")
        mock_queue.return_value = mock_q
        out = StringIO()
        call_command("renormalize_contracts", "--spec-version=3.1.0", stdout=out)
        mock_q.enqueue.assert_called_once()
        assert "rq-123" in out.getvalue()
