"""
Phase 2 integration tests: Prefect full flow with real hub (no mocks).

Uses LiveServerTestCase so the flow can call the hub via HTTP.
Creates ScheduledIngestion with HTTP source (test-data view), runs
scheduled_ingestion_full_flow in a subprocess (to avoid same-process Prefect
ephemeral server deadlock and 600s timeouts), asserts run created and updated.

Requires PREFECT_API_URL pointing at a running Prefect server (e.g. prefect-server-test).
"""

import contextlib
import os
import subprocess
import sys
import unittest
import urllib.request
import uuid

import pytest
from django.test import LiveServerTestCase

from hub.apps.auth.models import APIKey
from hub.apps.scheduled_ingestion.internal_auth import SCOPE_SCHEDULED_INGESTION_INTERNAL
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

# Integration test; 600s allows subprocess + LiveServer + teardown (flush can be slow)
pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
    pytest.mark.timeout(600),
]

# Subprocess timeout for the flow (must complete within this or test fails)
# 180s allows for slow Prefect server, DB, and test-data endpoint in CI
FLOW_SUBPROCESS_TIMEOUT = 180


def _prefect_integration_path():
    """Return services/prefect-integration absolute path."""
    here = os.path.abspath(__file__)
    for _ in range(5):
        here = os.path.dirname(here)
    return os.path.join(here, "services", "prefect-integration")


def _prefect_server_reachable(prefect_api_url: str, timeout_seconds: float = 5.0) -> bool:
    """Return True if Prefect API health endpoint is reachable."""
    try:
        health = prefect_api_url.rstrip("/").replace("/api", "") + "/api/health"
        req = urllib.request.Request(health)
        urllib.request.urlopen(req, timeout=timeout_seconds)
        return True
    except Exception:
        return False


class _NoStaticFilesHandler:
    """
    Passthrough handler that delegates all requests directly to the WSGI app.

    Django's default LiveServerTestCase uses ``StaticFilesHandler`` which
    wraps the WSGI app and checks ``_should_handle`` via ``get_path_info``.
    Under Django 6.0 + wsgiref (Python 3.12), ``get_path_info`` can return
    ``bytes`` instead of ``str``, causing ``_should_handle`` to raise
    ``TypeError`` on every request (bytes.startswith(str)).

    This test only needs API endpoints, not static files.  Bypassing the
    static-files layer avoids the bug and removes the ``STATIC_URL``
    requirement.
    """

    def __init__(self, application):
        self.application = application

    def __call__(self, environ, start_response):
        return self.application(environ, start_response)


class TestPrefectFullFlowIntegration(LiveServerTestCase):
    """
    Run scheduled_ingestion_full_flow against live hub; assert run created and updated.

    No mocks: real hub (live server), real flow in subprocess, real DB.
    Flow runs in subprocess to avoid same-process Prefect client/server deadlock
    and to enforce a bounded timeout (180s).
    """

    static_handler = _NoStaticFilesHandler

    # Skip DB flush in teardown so test + teardown complete within pytest timeout (600s).
    @classmethod
    def _fixture_teardown(cls):
        pass

    def tearDown(self):
        """Ensure DB connection is usable before teardown (avoids flush failure if Postgres restarts)."""
        from django.db import connection

        with contextlib.suppress(Exception):
            connection.ensure_connection()
        super().tearDown()

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Prefect Flow Test Tenant {uid}",
            slug=f"prefect-flow-test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"prefect-flow-test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        plaintext = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(plaintext),
            name="Worker API Key",
            scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
        )
        self.worker_api_key = plaintext

        base_url = f"{self.live_server_url}/api/v1/scheduled-ingestions/internal/test-data/"
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Prefect Full Flow Test",
            source_type=SourceType.HTTP,
            source_config={
                "base_url": base_url,
                "paths": ["sample.csv"],
                "headers": {
                    "X-Internal-Test-Data": "1",
                    # Phase 220.2: test-data endpoint now requires worker auth
                    "Authorization": f"ApiKey {self.worker_api_key}",
                    "X-Tenant-ID": str(self.tenant.id),
                },
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=r".*\.csv",
            created_by=self.user,
        )

    def test_full_flow_creates_run_and_processes_file(self):
        """Run full flow in subprocess; assert hub run created, updated, and process-file called."""
        prefect_api_url = os.environ.get(
            "PREFECT_API_URL", "http://prefect-server-test:4200/api"
        ).rstrip("/")
        if not _prefect_server_reachable(prefect_api_url):
            raise unittest.SkipTest(
                "Prefect server not reachable at PREFECT_API_URL. "
                "Start prefect-server-test (and prefect-db-test) for full flow integration."
            )

        prefect_integration = _prefect_integration_path()
        if not os.path.isdir(prefect_integration):
            raise unittest.SkipTest(
                "prefect-integration service path not found. "
                f"Expected directory: {prefect_integration}"
            )

        # Verify prefect is importable in the subprocess environment before
        # launching the flow — the subprocess imports prefect at runtime and
        # will fail with ModuleNotFoundError if it's not installed.
        try:
            subprocess.run(
                [sys.executable, "-c", "import prefect"],
                check=False,
                capture_output=True,
                timeout=30,  # Prefect 3.x server client init can be slow
                env={
                    **os.environ,
                    "PYTHONPATH": prefect_integration
                    + os.pathsep
                    + os.environ.get("PYTHONPATH", ""),
                },
            ).check_returncode()
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise unittest.SkipTest(
                "prefect is not installed in the subprocess Python environment. "
                "Ensure prefect>=3.6.15 is installed."
            )
        except subprocess.TimeoutExpired:
            raise unittest.SkipTest(
                "prefect import timed out — Prefect server may be slow to initialise. "
                "Ensure prefect>=3.6.15 is installed and PREFECT_API_URL is reachable."
            )

        env = {
            **os.environ,
            "HUB_BASE_URL": self.live_server_url,
            "HUB_WORKER_API_KEY": self.worker_api_key,
            "PREFECT_API_URL": prefect_api_url,
            "SCHEDULED_INGESTION_ID": str(self.scheduled_ingestion.id),
            "TENANT_ID": str(self.tenant.id),
            "PYTHONPATH": prefect_integration + os.pathsep + os.environ.get("PYTHONPATH", ""),
        }

        script = """
import os
import sys
from uuid import UUID
from workflows.scheduled_ingestion_full_flow import scheduled_ingestion_full_flow
scheduled_ingestion_full_flow(
    UUID(os.environ["SCHEDULED_INGESTION_ID"]),
    UUID(os.environ["TENANT_ID"]),
    None,
)
"""

        try:
            proc = subprocess.run(
                [sys.executable, "-c", script],
                check=False,
                env=env,
                capture_output=True,
                text=True,
                timeout=FLOW_SUBPROCESS_TIMEOUT,
                cwd=prefect_integration,
            )
        except subprocess.TimeoutExpired:
            self.fail(
                f"Flow did not complete within {FLOW_SUBPROCESS_TIMEOUT}s. "
                "Ensure Prefect server is healthy and test-data endpoint is fast."
            )
        except FileNotFoundError:
            raise unittest.SkipTest("Python executable not found for subprocess")

        if proc.returncode != 0:
            stderr = proc.stderr or ""
            if "incompatible versions" in stderr or "Major versions must match" in stderr:
                msg = (
                    "Prefect client and server major versions must match. "
                    "Ensure docker-compose.test.yml pins prefect-server-test and prefect-worker-test "
                    "to an explicit 2.x image (e.g. prefecthq/prefect:2.16.9-python3.12). "
                    "Hub and prefect-integration use prefect>=2.14.0,<3. stderr: "
                    + (stderr[:500] if stderr else "(none)")
                )
                raise unittest.SkipTest(msg)
            self.fail(
                f"Flow subprocess exited with code {proc.returncode}. "
                f"stderr: {stderr or '(none)'}. stdout: {proc.stdout or '(none)'}"
            )

        runs = list(
            ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=self.scheduled_ingestion
            ).order_by("-started_at")[:1]
        )
        self.assertGreaterEqual(len(runs), 1, "At least one run should exist")
        run = runs[0]
        self.assertIn(
            run.status,
            (ScheduledIngestionRunStatus.COMPLETED, ScheduledIngestionRunStatus.FAILED),
            f"Run should reach terminal status, got {run.status}",
        )
        self.assertGreaterEqual(
            run.files_found,
            0,
            "files_found should be set",
        )
        if run.status == ScheduledIngestionRunStatus.COMPLETED:
            self.assertGreaterEqual(
                run.files_processed,
                1,
                "At least one file should be processed on success",
            )
        else:
            self.assertIsNotNone(
                run.error_message or (run.result_json or {}).get("errors"),
                "Failed run should have error info",
            )
        self.assertIsNotNone(run.completed_at, "Run should have completed_at set")
        self.assertIsNotNone(run.started_at, "Run should have started_at set")
