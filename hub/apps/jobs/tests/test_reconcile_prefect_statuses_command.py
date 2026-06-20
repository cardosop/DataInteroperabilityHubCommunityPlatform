"""
Phase 83.3 — reconcile_prefect_statuses management command tests.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase


@pytest.mark.django_db(transaction=True)
class ReconcilePrefectStatusesCommandTest(TestCase):
    @patch("hub.apps.jobs.tasks_prefect_sync.reconcile_prefect_run_statuses", return_value=3)
    def test_reconciles_stale_runs(self, mock_reconcile):
        out = StringIO()
        call_command("reconcile_prefect_statuses", stdout=out)
        mock_reconcile.assert_called_once()
        assert "3" in out.getvalue()

    @patch("hub.apps.jobs.tasks_prefect_sync.reconcile_prefect_run_statuses", return_value=0)
    def test_zero_stale_runs_clean_exit(self, mock_reconcile):
        out = StringIO()
        call_command("reconcile_prefect_statuses", stdout=out)
        assert "0" in out.getvalue()

    @patch(
        "hub.apps.jobs.tasks_prefect_sync.reconcile_prefect_run_statuses",
        side_effect=ConnectionError("Prefect down"),
    )
    def test_service_unavailable_raises(self, mock_reconcile):
        with self.assertRaises(ConnectionError):
            call_command("reconcile_prefect_statuses")
