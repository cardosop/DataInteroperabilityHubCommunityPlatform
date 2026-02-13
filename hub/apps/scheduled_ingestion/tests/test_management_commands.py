"""
Tests for Scheduled Ingestion Management Commands

Tests for detect_and_remediate_stuck_runs management command.
No mocks: Prefect API is exercised via a real in-process HTTP server.
"""

import json
import os
import socket
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from uuid import uuid4

import pytest
from django.core.management import call_command
from django.test import TransactionTestCase
from django.utils import timezone

from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
]


def _start_fake_prefect_api_server(state_type: str):
    """
    Start a real HTTP server that responds to GET /flow_runs/<id> with
    JSON { "id": <id>, "state_type": state_type, "name": "..." }.
    Returns (base_url, server, thread). Caller sets PREFECT_API_URL=base_url
    and must shutdown server and join thread when done.
    """

    class PrefectFlowRunHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/flow_runs/"):
                run_id = self.path.split("/flow_runs/", 1)[-1].split("/")[0]
                body = {
                    "id": run_id,
                    "state_type": state_type,
                    "name": "scheduled_ingestion_full_flow",
                }
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), PrefectFlowRunHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    return base_url, server, thread


class TestDetectAndRemediateStuckRuns(TransactionTestCase):
    """Tests for detect_and_remediate_stuck_runs management command."""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for tests."""
        # Skip flush to avoid foreign key constraint issues
        pass

    def setUp(self):
        """Set up test data."""
        # Clean up any existing stuck runs from previous tests
        # This ensures test isolation
        ScheduledIngestionRun.objects.filter(status=ScheduledIngestionRunStatus.RUNNING).delete()

        # Create tenant with unique name
        unique_id = uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique_id}",
            slug=f"test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create scheduled ingestion
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "path": "test/"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "02:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

    def test_no_stuck_runs(self):
        """Test command when no stuck runs exist."""
        out = StringIO()
        err = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out, stderr=err)
        output = out.getvalue()
        self.assertIn("No stuck runs found", output)

    def test_detect_stuck_run_no_prefect_flow_id(self):
        """Test detection of stuck run without Prefect flow_run_id."""
        # Create a stuck run (RUNNING for > 2 hours)
        stuck_time = timezone.now() - timedelta(hours=3)
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id=None,
        )

        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out, dry_run=True)
        output = out.getvalue()
        self.assertIn("Found 1 stuck run(s)", output)
        self.assertIn(str(run.id), output)
        self.assertIn("[DRY RUN]", output)

        # Verify run not updated in dry-run mode
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.RUNNING)

    def test_remediate_stuck_run_no_prefect_flow_id(self):
        """Test remediation of stuck run without Prefect flow_run_id."""
        # Create a stuck run (RUNNING for > 2 hours)
        stuck_time = timezone.now() - timedelta(hours=3)
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id=None,
        )

        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out)
        output = out.getvalue()
        self.assertIn("Found 1 stuck run(s)", output)
        self.assertIn("Marked hub run as FAILED", output)

        # Verify run updated
        run.refresh_from_db()
        self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
        self.assertIsNotNone(run.completed_at)
        self.assertIn("Prefect flow run not found", run.error_message)

    def test_remediate_stuck_run_prefect_flow_failed(self):
        """Test remediation when Prefect flow run is FAILED (real HTTP server)."""
        stuck_time = timezone.now() - timedelta(hours=3)
        prefect_flow_run_id = "prefect-flow-run-123"
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id=prefect_flow_run_id,
        )

        base_url, server, _ = _start_fake_prefect_api_server("FAILED")
        prev = os.environ.get("PREFECT_API_URL")
        try:
            os.environ["PREFECT_API_URL"] = base_url
            out = StringIO()
            call_command("detect_and_remediate_stuck_runs", stdout=out)
            output = out.getvalue()
            self.assertIn("Found 1 stuck run(s)", output)
            self.assertIn("Updated hub run to FAILED", output)
            run.refresh_from_db()
            self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
            self.assertIsNotNone(run.completed_at)
            self.assertIn("prefect flow run failed", run.error_message.lower())
            self.assertIn("hub run status updated", run.error_message.lower())
        finally:
            server.shutdown()
            if prev is not None:
                os.environ["PREFECT_API_URL"] = prev
            else:
                os.environ.pop("PREFECT_API_URL", None)

    def test_remediate_stuck_run_prefect_flow_cancelled(self):
        """Test remediation when Prefect flow run is CANCELLED (real HTTP server)."""
        stuck_time = timezone.now() - timedelta(hours=3)
        prefect_flow_run_id = "prefect-flow-run-456"
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id=prefect_flow_run_id,
        )

        base_url, server, _ = _start_fake_prefect_api_server("CANCELLED")
        prev = os.environ.get("PREFECT_API_URL")
        try:
            os.environ["PREFECT_API_URL"] = base_url
            out = StringIO()
            call_command("detect_and_remediate_stuck_runs", stdout=out)
            output = out.getvalue()
            self.assertIn("Found 1 stuck run(s)", output)
            self.assertIn("Updated hub run to CANCELLED", output)
            run.refresh_from_db()
            self.assertEqual(run.status, ScheduledIngestionRunStatus.CANCELLED)
            self.assertIsNotNone(run.completed_at)
            self.assertIn("prefect flow run cancelled", run.error_message.lower())
            self.assertIn("hub run status updated", run.error_message.lower())
        finally:
            server.shutdown()
            if prev is not None:
                os.environ["PREFECT_API_URL"] = prev
            else:
                os.environ.pop("PREFECT_API_URL", None)

    def test_remediate_stuck_run_prefect_flow_still_running(self):
        """Test remediation when Prefect flow run is still RUNNING (real HTTP server)."""
        stuck_time = timezone.now() - timedelta(hours=3)
        prefect_flow_run_id = "prefect-flow-run-789"
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id=prefect_flow_run_id,
        )

        base_url, server, _ = _start_fake_prefect_api_server("RUNNING")
        prev = os.environ.get("PREFECT_API_URL")
        try:
            os.environ["PREFECT_API_URL"] = base_url
            out = StringIO()
            call_command("detect_and_remediate_stuck_runs", stdout=out)
            output = out.getvalue()
            self.assertIn("Found 1 stuck run(s)", output)
            self.assertIn("Marked hub run as FAILED (stuck)", output)
            run.refresh_from_db()
            self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
            self.assertIsNotNone(run.completed_at)
            self.assertIn("stuck run detected", run.error_message.lower())
            self.assertIn("prefect flow still running", run.error_message.lower())
        finally:
            server.shutdown()
            if prev is not None:
                os.environ["PREFECT_API_URL"] = prev
            else:
                os.environ.pop("PREFECT_API_URL", None)

    def test_remediate_stuck_run_prefect_api_unreachable(self):
        """Test remediation when Prefect API is unreachable (no server, no mocks)."""
        stuck_time = timezone.now() - timedelta(hours=3)
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
            prefect_flow_run_id="prefect-flow-run-999",
        )

        # Point to a port that has no server → connection refused (real failure)
        prev = os.environ.get("PREFECT_API_URL")
        try:
            os.environ["PREFECT_API_URL"] = "http://127.0.0.1:19999"
            out = StringIO()
            call_command("detect_and_remediate_stuck_runs", stdout=out)
            output = out.getvalue()
            self.assertIn("Found 1 stuck run(s)", output)
            self.assertIn("Marked hub run as FAILED", output)
            run.refresh_from_db()
            self.assertEqual(run.status, ScheduledIngestionRunStatus.FAILED)
            self.assertIsNotNone(run.completed_at)
            self.assertIn("prefect flow run not found", run.error_message.lower())
            self.assertIn("stuck run detected", run.error_message.lower())
        finally:
            if prev is not None:
                os.environ["PREFECT_API_URL"] = prev
            else:
                os.environ.pop("PREFECT_API_URL", None)

    def test_custom_threshold_hours(self):
        """Test command with custom threshold hours."""
        # Create a run that's stuck for 1 hour (below default 2h threshold)
        stuck_time = timezone.now() - timedelta(hours=1)
        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
        )

        # With default threshold (2h), should not detect
        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out)
        output = out.getvalue()
        self.assertIn("No stuck runs found", output)

        # With custom threshold (0.5h), should detect
        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", threshold_hours=0.5, stdout=out)
        output = out.getvalue()
        self.assertIn("Found 1 stuck run(s)", output)

    def test_multiple_stuck_runs(self):
        """Test command with multiple stuck runs."""
        # Create multiple stuck runs
        stuck_time = timezone.now() - timedelta(hours=3)
        for i in range(3):
            ScheduledIngestionRun.objects.create(
                scheduled_ingestion=self.scheduled_ingestion,
                status=ScheduledIngestionRunStatus.RUNNING,
                started_at=stuck_time,
            )

        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out, dry_run=True)
        output = out.getvalue()
        self.assertIn("Found 3 stuck run(s)", output)

        # Verify runs not updated in dry-run mode
        stuck_runs = ScheduledIngestionRun.objects.filter(
            status=ScheduledIngestionRunStatus.RUNNING
        )
        self.assertEqual(stuck_runs.count(), 3)

    def test_non_stuck_runs_not_affected(self):
        """Test that non-stuck runs are not affected."""
        # Create a run that's not stuck (RUNNING for < 2 hours)
        recent_time = timezone.now() - timedelta(hours=1)
        recent_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=recent_time,
        )

        # Create a completed run
        completed_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=3),
            completed_at=timezone.now() - timedelta(hours=2),
        )

        # Create a stuck run
        stuck_time = timezone.now() - timedelta(hours=3)
        stuck_run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            status=ScheduledIngestionRunStatus.RUNNING,
            started_at=stuck_time,
        )

        out = StringIO()
        call_command("detect_and_remediate_stuck_runs", stdout=out)
        output = out.getvalue()
        self.assertIn("Found 1 stuck run(s)", output)

        # Verify only stuck run was updated
        recent_run.refresh_from_db()
        completed_run.refresh_from_db()
        stuck_run.refresh_from_db()

        self.assertEqual(recent_run.status, ScheduledIngestionRunStatus.RUNNING)
        self.assertEqual(completed_run.status, ScheduledIngestionRunStatus.COMPLETED)
        self.assertEqual(stuck_run.status, ScheduledIngestionRunStatus.FAILED)
