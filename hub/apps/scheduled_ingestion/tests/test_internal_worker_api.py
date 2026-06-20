"""
Phase 1 tests for Internal Worker API (run lifecycle, process-file, config, auth).

No mocks: real DB, real ScheduledIngestionRun, real services (CostTrackingManager, DLQ, etc.).

Uses TestCase with unique tenant/slug and user email per run to avoid duplicate-key errors
and to avoid TransactionTestCase teardown flush timeouts.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
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

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(120),
]


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    key_hash = APIKey.hash_key(plaintext)
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=key_hash,
        name="Worker API Key",
        scopes=[SCOPE_SCHEDULED_INGESTION_INTERNAL],
    )
    return plaintext


class InternalWorkerAPITest(TestCase):
    """
    Internal Worker API tests: run lifecycle, auth, config masking, internal job creation.

    Uses unique tenant name/slug and user email per test run to avoid duplicate-key
    errors when using --reuse-db or parallel runs.
    """

    def setUp(self):
        self.client = APIClient()
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Worker Test Tenant {unique}",
            slug=f"worker-test-tenant-{unique}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"worker-test-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Worker Test Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "send_notifications": False,
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )
        self.config_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Config Test Ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "secret-bucket",
                "secret_access_key": "very-secret-key-value",
                "access_key_id": "AKIA_SECRET_ID",
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*",
            created_by=self.user,
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}")

    # --- Run lifecycle ---

    def test_create_run_201(self):
        """POST internal/runs/ creates ScheduledIngestionRun with status RUNNING."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "RUNNING")
        run = ScheduledIngestionRun.objects.get(id=response.data["id"])
        self.assertEqual(run.scheduled_ingestion_id, self.scheduled_ingestion.id)
        self.assertEqual(run.status, ScheduledIngestionRunStatus.RUNNING)
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="CREATED",
            resource_id=str(run.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_create_run_idempotency_prefect_flow_run_id(self):
        """Same prefect_flow_run_id returns 200 with existing run."""
        self._auth()
        payload = {
            "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
            "prefect_flow_run_id": "pf-run-123",
        }
        r1 = self.client.post("/api/v1/scheduled-ingestions/internal/runs/", payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        run_id = r1.data["id"]
        r2 = self.client.post("/api/v1/scheduled-ingestions/internal/runs/", payload, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["id"], run_id)
        self.assertEqual(
            ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=self.scheduled_ingestion
            ).count(),
            1,
        )

    def test_patch_run_completed_side_effects(self):
        """PATCH run to COMPLETED updates next_run_at, cost, DLQ sync, notification path."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        run_id = r_create.data["id"]
        run = ScheduledIngestionRun.objects.get(id=run_id)
        run.files_found = 1
        run.files_processed = 1
        run.files_failed = 0
        run.save()
        response = self.client.patch(
            f"/api/v1/scheduled-ingestions/internal/runs/{run_id}/",
            {"status": "COMPLETED", "completed_at": timezone.now().isoformat()},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.scheduled_ingestion.refresh_from_db()
        self.assertIsNotNone(self.scheduled_ingestion.next_run_at)
        from hub.apps.scheduled_ingestion.models import IngestionCost

        cost_exists = IngestionCost.objects.filter(run_id=run_id).exists()
        self.assertTrue(cost_exists, "Cost record should be created on COMPLETED")

    # --- Auth ---

    def test_reject_missing_token(self):
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(response.content, f"Response body must be non-empty for {response.status_code}")

    def test_reject_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="ApiKey invalid-key-12345")
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertTrue(response.content, f"Response body must be non-empty for {response.status_code}")

    def test_reject_token_without_scope(self):
        plaintext = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=APIKey.hash_key(plaintext),
            name="No Scope Key",
            scopes=["assets:read"],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.content, f"Response body must be non-empty for {response.status_code}")

    def test_reject_run_from_different_tenant(self):
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )
        plaintext = _create_worker_api_key(other_tenant, other_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(response.content, f"Response body must be non-empty for {response.status_code}")

    # --- Config and internal job ---

    def test_config_masks_credentials(self):
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/internal/config/{self.config_ingestion.id}/",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        source_config = response.data.get("source_config", {})
        self.assertNotIn("very-secret-key-value", str(source_config))
        self.assertNotIn("AKIA_SECRET_ID", str(source_config))
        self.assertIn("source_type", response.data)
        self.assertIn("file_pattern", response.data)

    def test_internal_create_job_creates_prefect_executed_job(self):
        """POST internal/jobs/ creates Job with executed_by_prefect; no RQ enqueue."""
        self._auth()
        payload = {
            "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
            "prefect_flow_run_id": "prefect-flow-run-123",
            "scheduled_ingestion_run_id": None,
        }
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/jobs/",
            payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertTrue(response.data.get("executed_by_prefect"))
        self.assertEqual(response.data.get("prefect_flow_run_id"), "prefect-flow-run-123")
        from hub.apps.jobs.models import Job

        job = Job.objects.get(id=response.data["id"])
        self.assertEqual(job.type, "SCHEDULED_INGESTION")
        self.assertTrue(job.details_json.get("executed_by_prefect"))
        self.assertEqual(job.details_json.get("prefect_flow_run_id"), "prefect-flow-run-123")

    # --- Process-file (Phase 5: audit, domain events, metrics) ---

    def test_process_file_success_emits_audit_and_returns_201(self):
        """POST process-file/ with valid file returns 201 and emits audit PROCESSED."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        run_id = r_create.data["id"]
        csv_content = b"id,name\n1,alpha\n2,beta\n"
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/process-file/",
            {
                "run_id": run_id,
                "file_path": "data/sample.csv",
                "file_content": __import__("base64").b64encode(csv_content).decode(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("file_id", response.data)
        self.assertIn("dataset_id", response.data)
        file_id = response.data["file_id"]
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_FILE",
            action="PROCESSED",
            resource_id=file_id,
        ).first()
        self.assertIsNotNone(audit, "audit PROCESSED for file required")
        details = getattr(audit, "details_json", None) or getattr(audit, "details", None) or {}
        self.assertIn("run_id", details, "audit should include run_id in details")
        self.assertEqual(str(details.get("run_id")), str(run_id))

    # --- Edge cases and error handling ---

    def test_create_run_invalid_scheduled_ingestion_id_returns_400_or_404(self):
        """POST internal/runs/ with non-existent scheduled_ingestion_id returns error."""
        self._auth()

        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(uuid.uuid4())},
            format="json",
        )
        msg = getattr(response, "data", None) or getattr(response, "content", b"")
        if hasattr(msg, "decode"):
            msg = msg.decode("utf-8", errors="replace") if msg else ""
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND),
            msg,
        )

    def test_create_run_missing_scheduled_ingestion_id_returns_400(self):
        """POST internal/runs/ without scheduled_ingestion_id returns 400."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_config_non_existent_ingestion_returns_404(self):
        """GET internal/config/{id}/ for non-existent id returns 404."""
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/internal/config/{uuid.uuid4()}/",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(response.content, f"Response body must be non-empty for {response.status_code}")

    def test_patch_run_invalid_status_returns_400(self):
        """PATCH run with invalid status value returns 400."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        run_id = r_create.data["id"]
        response = self.client.patch(
            f"/api/v1/scheduled-ingestions/internal/runs/{run_id}/",
            {"status": "INVALID_STATUS"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY),
            response.data,
        )
