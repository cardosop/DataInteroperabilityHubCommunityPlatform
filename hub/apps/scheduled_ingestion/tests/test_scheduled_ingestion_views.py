"""
Unit tests for Scheduled Ingestion API views

Tests for CRUD operations, run history, and manual trigger endpoints.
No mocks: trigger tests use a real in-process HTTP server for the
Prefect integration service contract.
"""

import json
import os
import socket
import threading
import uuid
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


def _start_fake_prefect_trigger_server(flow_run_id):
    """
    Start a real HTTP server in a thread that responds to POST /deployments/trigger
    with 200 and {"flow_run_id": flow_run_id}. Returns (base_url, server_thread).
    Caller must set PREFECT_INTEGRATION_SERVICE_URL=base_url and later join the thread.
    """
    flow_run_id_str = str(flow_run_id)

    class TriggerHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path.rstrip("/") == "/deployments/trigger":
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"flow_run_id": flow_run_id_str}).encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, format, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), TriggerHandler)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"
    return base_url, server, thread


def _scheduled_ingestion_kwargs(tenant, user, **overrides):
    """Minimum required kwargs for ScheduledIngestion.objects.create (schedule_type/schedule_config/file_pattern)."""
    kwargs = {
        "tenant": tenant,
        "name": overrides.get("name", "Test Ingestion"),
        "source_type": SourceType.S3,
        "source_config": {"bucket": "test-bucket"},
        "schedule_type": ScheduleType.DAILY,
        "schedule_config": {"time": "00:00"},
        "file_pattern": ".*\\.csv",
        "created_by": user,
    }
    kwargs.update(overrides)
    return kwargs


class ScheduledIngestionViewSetTest(TestCase):
    """Test ScheduledIngestionViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant (VERIFIED for plan limits / scheduled ingestion creation)
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)

    def test_create_scheduled_ingestion(self):
        """Test creating a scheduled ingestion (schedule_type/schedule_config/file_pattern)."""
        data = {
            "name": "Daily Sales Ingestion",
            "description": "Ingests daily sales CSV files",
            "source_type": "S3",
            "source_config": {
                "bucket": "my-data-lake",
                "prefix": "sales/daily/",
                "access_key_id": "AKIA...",
                "secret_access_key": "abc...",
            },
            "schedule_type": ScheduleType.DAILY,
            "schedule_config": {"time": "02:00"},
            "file_pattern": "sales_\\d{4}-\\d{2}-\\d{2}\\.csv",
            "auto_create_asset": True,
            "auto_activate": True,
            "status": "ACTIVE",
            "test_connection": False,
        }

        response = self.client.post("/api/v1/scheduled-ingestions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "Daily Sales Ingestion")
        self.assertEqual(response.data["source_type"], "S3")
        self.assertIn("id", response.data)

        ingestion = ScheduledIngestion.objects.get(id=response.data["id"])
        self.assertEqual(ingestion.tenant, self.tenant)
        self.assertEqual(ingestion.created_by, self.user)

    def test_create_scheduled_ingestion_invalid_cron(self):
        """Test creating scheduled ingestion with invalid cron (schedule_config for CUSTOM_CRON)."""
        data = {
            "name": "Test Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "test-bucket"},
            "schedule_type": ScheduleType.CUSTOM_CRON,
            "schedule_config": {"cron": "invalid cron"},
            "file_pattern": ".*\\.csv",
        }

        response = self.client.post("/api/v1/scheduled-ingestions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            "schedule_config" in response.data or "schedule" in str(response.data).lower(),
            f"Expected schedule_config or schedule in error: {response.data}",
        )

    def test_create_scheduled_ingestion_invalid_regex(self):
        """Test creating scheduled ingestion with invalid regex pattern"""
        data = {
            "name": "Test Ingestion",
            "source_type": "S3",
            "source_config": {"bucket": "test-bucket"},
            "schedule": "0 0 * * *",
            "file_pattern": "[invalid regex",
        }

        response = self.client.post("/api/v1/scheduled-ingestions/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("file_pattern", response.data)

    def test_list_scheduled_ingestions(self):
        """Test listing scheduled ingestions (paginated or list)."""
        ingestion1 = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user, name="Ingestion 1")
        )
        ingestion2 = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(
                self.tenant,
                self.user,
                name="Ingestion 2",
                source_type=SourceType.GCS,
                source_config={"bucket": "bucket2"},
            )
        )

        response = self.client.get("/api/v1/scheduled-ingestions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(results), 2)
        names = [item["name"] for item in results]
        self.assertIn("Ingestion 1", names)
        self.assertIn("Ingestion 2", names)

    def test_retrieve_scheduled_ingestion(self):
        """Test retrieving a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user)
        )

        response = self.client.get(f"/api/v1/scheduled-ingestions/{ingestion.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Ingestion")
        self.assertEqual(response.data["id"], str(ingestion.id))

    def test_update_scheduled_ingestion(self):
        """Test updating a scheduled ingestion (schedule_config, not schedule)."""
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user)
        )

        data = {
            "description": "Updated description",
            "schedule_config": {"time": "03:00"},
        }

        response = self.client.patch(
            f"/api/v1/scheduled-ingestions/{ingestion.id}/", data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["description"], "Updated description")
        self.assertEqual(response.data["schedule_config"].get("time"), "03:00")

        ingestion.refresh_from_db()
        self.assertEqual(ingestion.description, "Updated description")
        self.assertEqual(ingestion.schedule_config.get("time"), "03:00")

    def test_delete_scheduled_ingestion(self):
        """Test deleting a scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user),
            prefect_deployment_id=uuid.uuid4(),
        )

        response = self.client.delete(f"/api/v1/scheduled-ingestions/{ingestion.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ScheduledIngestion.objects.filter(id=ingestion.id).exists())

    def test_list_runs(self):
        """Test listing runs for a scheduled ingestion (paginated or list)."""
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user)
        )

        run1 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1),
        )
        run2 = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.FAILED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            error_message="Processing failed",
        )

        response = self.client.get(f"/api/v1/scheduled-ingestions/{ingestion.id}/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        self.assertEqual(len(results), 2)
        statuses = [item["status"] for item in results]
        self.assertIn("COMPLETED", statuses)
        self.assertIn("FAILED", statuses)

    def test_retrieve_run(self):
        """Test retrieving a specific run"""
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(self.tenant, self.user)
        )

        run = ScheduledIngestionRun.objects.create(
            scheduled_ingestion=ingestion,
            status=ScheduledIngestionRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            result_json={"files_processed": 5, "datasets_created": 5},
        )

        # Retrieve run via flat runs endpoint: /api/v1/scheduled-ingestions/runs/{run_id}/
        response = self.client.get(f"/api/v1/scheduled-ingestions/runs/{run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["id"], str(run.id))
        self.assertEqual(response.data["result_json"]["files_processed"], 5)

    def test_trigger_ingestion(self):
        """
        Trigger uses real HTTP call to PREFECT_INTEGRATION_SERVICE_URL.
        Uses in-process HTTP server (no mocks) to verify view behavior.
        """
        flow_run_id = uuid.uuid4()
        base_url, server, thread = _start_fake_prefect_trigger_server(flow_run_id)
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        try:
            prev = os.environ.get("PREFECT_INTEGRATION_SERVICE_URL")
            os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = base_url
            try:
                response = self.client.post(f"/api/v1/scheduled-ingestions/{ingestion.id}/trigger/")
            finally:
                if prev is None:
                    os.environ.pop("PREFECT_INTEGRATION_SERVICE_URL", None)
                else:
                    os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = prev
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertIn("flow_run_id", response.data)
            self.assertIn("scheduled_ingestion_run_id", response.data)
            run = ScheduledIngestionRun.objects.get(
                scheduled_ingestion=ingestion,
                prefect_flow_run_id=flow_run_id,
            )
            self.assertEqual(run.status, ScheduledIngestionRunStatus.PENDING)
        finally:
            server.shutdown()

    def test_trigger_does_not_enqueue_scheduled_ingestion(self):
        """
        Phase 3.3: Trigger starts flow via integration service; no RQ enqueue.
        Uses real in-process HTTP server (no mocks).
        """
        from django_rq import get_queue

        flow_run_id = uuid.uuid4()
        base_url, server, thread = _start_fake_prefect_trigger_server(flow_run_id)
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Trigger No RQ Test",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        queue = get_queue("job_default")
        queue.empty()
        count_before = queue.count
        try:
            prev = os.environ.get("PREFECT_INTEGRATION_SERVICE_URL")
            os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = base_url
            try:
                response = self.client.post(f"/api/v1/scheduled-ingestions/{ingestion.id}/trigger/")
            finally:
                if prev is None:
                    os.environ.pop("PREFECT_INTEGRATION_SERVICE_URL", None)
                else:
                    os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = prev
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
            self.assertEqual(
                queue.count,
                count_before,
                "Trigger must not enqueue SCHEDULED_INGESTION to RQ",
            )
        finally:
            server.shutdown()

    def test_trigger_when_integration_service_url_not_configured(self):
        """Trigger returns 503 when PREFECT_INTEGRATION_SERVICE_URL is not set."""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )
        prev = os.environ.pop("PREFECT_INTEGRATION_SERVICE_URL", None)
        try:
            response = self.client.post(f"/api/v1/scheduled-ingestions/{ingestion.id}/trigger/")
            self.assertEqual(
                response.status_code,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                response.data,
            )
            self.assertIn("error", response.data)
        finally:
            if prev is not None:
                os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = prev

    def test_trigger_ingestion_not_active(self):
        """Test triggering a non-active scheduled ingestion"""
        ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            status=ScheduledIngestionStatus.PAUSED,
            created_by=self.user,
        )
        response = self.client.post(f"/api/v1/scheduled-ingestions/{ingestion.id}/trigger/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not active", response.data["detail"].lower())

    def test_tenant_isolation(self):
        """Test that tenants can only see their own scheduled ingestions (paginated or list)."""
        tenant2 = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        ingestion2 = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(
                tenant2,
                self.user,
                name="Other Ingestion",
                source_config={"bucket": "other-bucket"},
            )
        )

        response = self.client.get("/api/v1/scheduled-ingestions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        ingestion_ids = [item["id"] for item in results]
        self.assertNotIn(str(ingestion2.id), ingestion_ids)

    # --- Edge cases ---

    def test_list_filter_by_status(self):
        """List can be filtered by status query param."""
        ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(
                self.tenant, self.user, name="Active", status=ScheduledIngestionStatus.ACTIVE
            )
        )
        ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(
                self.tenant, self.user, name="Paused", status=ScheduledIngestionStatus.PAUSED
            )
        )
        response = self.client.get(
            "/api/v1/scheduled-ingestions/",
            {"status": ScheduledIngestionStatus.ACTIVE},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        for item in results:
            self.assertEqual(item["status"], ScheduledIngestionStatus.ACTIVE)

    def test_trigger_with_parameters(self):
        """Trigger accepts optional parameters in body."""
        flow_run_id = uuid.uuid4()
        base_url, server, _ = _start_fake_prefect_trigger_server(flow_run_id)
        ingestion = ScheduledIngestion.objects.create(
            **_scheduled_ingestion_kwargs(
                self.tenant, self.user, status=ScheduledIngestionStatus.ACTIVE
            )
        )
        try:
            prev = os.environ.get("PREFECT_INTEGRATION_SERVICE_URL")
            os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = base_url
            try:
                response = self.client.post(
                    f"/api/v1/scheduled-ingestions/{ingestion.id}/trigger/",
                    {"parameters": {"key": "value"}},
                    format="json",
                )
            finally:
                if prev is None:
                    os.environ.pop("PREFECT_INTEGRATION_SERVICE_URL", None)
                else:
                    os.environ["PREFECT_INTEGRATION_SERVICE_URL"] = prev
            self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        finally:
            server.shutdown()

    # --- Error handling ---

    def test_dashboard_requires_tenant(self):
        """Dashboard returns 400 when tenant cannot be resolved."""
        self.client.force_authenticate(user=None)
        self.client.credentials()
        # Anonymous or no-tenant user: tenant resolution may return None
        response = self.client.get("/api/v1/scheduled-ingestions/dashboard/")
        # Either 401 (unauthenticated) or 400 (tenant required)
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED),
            response.data,
        )

    def test_costs_invalid_start_date_returns_400(self):
        """Costs endpoint returns 400 for invalid start_date format."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/scheduled-ingestions/costs/",
            {"start_date": "not-a-date"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_costs_invalid_end_date_returns_400(self):
        """Costs endpoint returns 400 for invalid end_date format."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            "/api/v1/scheduled-ingestions/costs/",
            {"end_date": "invalid"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
