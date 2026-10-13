"""
Phase 1 tests for Internal Worker API (run lifecycle, process-file, config, auth).

No mocks: real DB, real ScheduledIngestionRun, real services (CostTrackingManager, DLQ, etc.).

Uses TestCase with unique tenant/slug and user email per run to avoid duplicate-key errors
and to avoid TransactionTestCase teardown flush timeouts.
"""

import uuid

import pytest
from django.test import TestCase, TransactionTestCase
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
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert response.data["status"] == "RUNNING"
        run = ScheduledIngestionRun.objects.get(id=response.data["id"])
        assert run.scheduled_ingestion_id == self.scheduled_ingestion.id
        assert run.status == ScheduledIngestionRunStatus.RUNNING
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_RUN",
            action="CREATED",
            resource_id=str(run.id),
        ).first()
        assert audit is not None

    def test_create_run_idempotency_prefect_flow_run_id(self):
        """Same prefect_flow_run_id returns 200 with existing run."""
        self._auth()
        payload = {
            "scheduled_ingestion_id": str(self.scheduled_ingestion.id),
            "prefect_flow_run_id": "pf-run-123",
        }
        r1 = self.client.post("/api/v1/scheduled-ingestions/internal/runs/", payload, format="json")
        assert r1.status_code == status.HTTP_201_CREATED
        run_id = r1.data["id"]
        r2 = self.client.post("/api/v1/scheduled-ingestions/internal/runs/", payload, format="json")
        assert r2.status_code == status.HTTP_200_OK
        assert r2.data["id"] == run_id
        assert (
            ScheduledIngestionRun.objects.filter(
                scheduled_ingestion=self.scheduled_ingestion
            ).count()
            == 1
        )

    def test_patch_run_completed_side_effects(self):
        """PATCH run to COMPLETED updates next_run_at, cost, DLQ sync, notification path."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert r_create.status_code == status.HTTP_201_CREATED
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
        assert response.status_code == status.HTTP_200_OK
        self.scheduled_ingestion.refresh_from_db()
        assert self.scheduled_ingestion.next_run_at is not None
        from hub.apps.scheduled_ingestion.models import IngestionCost

        cost_exists = IngestionCost.objects.filter(run_id=run_id).exists()
        assert cost_exists, "Cost record should be created on COMPLETED"

    # --- Auth ---

    def test_reject_missing_token(self):
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.content, f"Response body must be non-empty for {response.status_code}"

    def test_reject_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="ApiKey invalid-key-12345")
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert response.content, f"Response body must be non-empty for {response.status_code}"

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
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.content, f"Response body must be non-empty for {response.status_code}"

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
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.content, f"Response body must be non-empty for {response.status_code}"

    # --- Config and internal job ---

    def test_config_masks_credentials(self):
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/internal/config/{self.config_ingestion.id}/",
        )
        assert response.status_code == status.HTTP_200_OK
        source_config = response.data.get("source_config", {})
        assert "very-secret-key-value" not in str(source_config)
        assert "AKIA_SECRET_ID" not in str(source_config)
        assert "source_type" in response.data
        assert "file_pattern" in response.data

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
        assert response.status_code == status.HTTP_201_CREATED
        assert "id" in response.data
        assert response.data.get("executed_by_prefect")
        assert response.data.get("prefect_flow_run_id") == "prefect-flow-run-123"
        from hub.apps.jobs.models import Job

        job = Job.objects.get(id=response.data["id"])
        assert job.type == "SCHEDULED_INGESTION"
        assert job.details_json.get("executed_by_prefect")
        assert job.details_json.get("prefect_flow_run_id") == "prefect-flow-run-123"

    # --- Process-file (Phase 5: audit, domain events, metrics) ---

    def test_process_file_success_emits_audit_and_returns_201(self):
        """POST process-file/ with valid file returns 201 and emits audit PROCESSED."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert r_create.status_code == status.HTTP_201_CREATED
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
        assert response.status_code == status.HTTP_201_CREATED
        assert "file_id" in response.data
        assert "dataset_id" in response.data
        file_id = response.data["file_id"]
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_INGESTION_FILE",
            action="PROCESSED",
            resource_id=file_id,
        ).first()
        assert audit is not None, "audit PROCESSED for file required"
        details = getattr(audit, "details_json", None) or getattr(audit, "details", None) or {}
        assert "run_id" in details, "audit should include run_id in details"
        assert str(details.get("run_id")) == str(run_id)

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
        assert response.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND), msg

    def test_create_run_missing_scheduled_ingestion_id_returns_400(self):
        """POST internal/runs/ without scheduled_ingestion_id returns 400."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_config_non_existent_ingestion_returns_404(self):
        """GET internal/config/{id}/ for non-existent id returns 404."""
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-ingestions/internal/config/{uuid.uuid4()}/",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.content, f"Response body must be non-empty for {response.status_code}"

    def test_patch_run_invalid_status_returns_400(self):
        """PATCH run with invalid status value returns 400."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert r_create.status_code == status.HTTP_201_CREATED
        run_id = r_create.data["id"]
        response = self.client.patch(
            f"/api/v1/scheduled-ingestions/internal/runs/{run_id}/",
            {"status": "INVALID_STATUS"},
            format="json",
        )
        assert response.status_code in (
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        ), response.data


class WorkerKeyComparisonPin(TestCase):
    """Phase P.8 — the worker env key is a shared secret compared on every
    internal request; the comparison MUST be timing-safe (plain ``==``
    leaks prefix information over the network). Timing cannot be observed
    behaviorally, so the pin is source-level: a regression to ``==`` fails
    here. Both internal auth modules carry the same contract."""

    def test_worker_key_comparisons_are_timing_safe(self):
        from pathlib import Path

        for module in (
            "hub/apps/scheduled_ingestion/internal_auth.py",
            "hub/apps/scheduled_export/internal_auth.py",
        ):
            source = Path(module).read_text(encoding="utf-8")
            assert "compare_digest(api_key, worker_key)" in source, (
                f"{module} must compare the worker env key with hmac.compare_digest, not =="
            )
            assert "api_key == worker_key" not in source, (
                f"{module} regressed to a timing-unsafe comparison"
            )


class InternalWorkerFileHardeningTest(InternalWorkerAPITest):
    """W1.14 — per-file caps, extension validation, fail-closed auth.

    Subclasses the base class for the standard tenant/user/key/ingestion
    setUp (unique rows per test, safe on the shared DB).
    """

    def _create_run(self):
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert r_create.status_code == status.HTTP_201_CREATED, r_create.content
        return r_create.data["id"]

    def _post_file(self, run_id, file_path, content):
        return self.client.post(
            "/api/v1/scheduled-ingestions/internal/process-file/",
            {
                "run_id": run_id,
                "file_path": file_path,
                "file_content": __import__("base64").b64encode(content).decode(),
            },
            format="json",
        )

    def test_oversized_file_rejected(self):
        """A file over the per-file cap is rejected BEFORE processing."""
        from django.test import override_settings

        run_id = self._create_run()
        valid_csv = b"id,name\n" + b"1,alpha\n" * 600  # ~2.4 KB of valid CSV
        with override_settings(WORKER_INTERNAL_MAX_FILE_BYTES=1024):
            response = self._post_file(run_id, "data/sample.csv", valid_csv)
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        assert response.data.get("code") == "FILE_TOO_LARGE", response.content
        # W1.19 — convention 8: the enforcement emits its audit event.
        assert AuditEvent.objects.filter(
            action="WORKER_FILE_UPLOAD_REJECTED",
        ).exists()

    def test_unknown_extension_rejected(self):
        """Unknown extensions are REJECTED — never defaulted to CSV."""
        run_id = self._create_run()
        response = self._post_file(run_id, "data/dump.exe", b"id,name\n1,alpha\n")
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content
        assert response.data.get("code") == "UNSUPPORTED_FORMAT", response.content
        # W1.19 — convention 8: the enforcement emits its audit event.
        assert AuditEvent.objects.filter(
            action="WORKER_FILE_UPLOAD_REJECTED",
        ).exists()

    def test_extensionless_path_rejected(self):
        run_id = self._create_run()
        response = self._post_file(run_id, "data/dump", b"id,name\n1,alpha\n")
        assert response.status_code == status.HTTP_400_BAD_REQUEST, response.content

    def test_no_key_fail_closed_with_env_key_unset(self):
        """HUB_WORKER_API_KEY unset -> 401 for EVERY credential — there is
        no dev fallback accepting a default key."""
        from django.test import override_settings

        with override_settings(HUB_WORKER_API_KEY=None):
            no_creds = APIClient()
            resp = no_creds.post(
                "/api/v1/scheduled-ingestions/internal/runs/",
                {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
                format="json",
            )
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED

            bogus = APIClient()
            bogus.credentials(HTTP_AUTHORIZATION="ApiKey dev-fallback-key")
            resp = bogus.post(
                "/api/v1/scheduled-ingestions/internal/runs/",
                {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
                format="json",
            )
            assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_db_api_key_tenant_mismatch_rejected(self):
        """A tenant-scoped DB API key + a FOREIGN X-Tenant-ID header is
        REJECTED (403) by the tenant-scoping middleware — the tenant is
        bound to the authenticated credential, never the free header.
        (The pre-audit hypothesis was that the key silently re-scoped;
        the actual enforcement rejects the mismatch, which is the
        stronger contract — pinned as such.)"""
        other_tenant = Tenant.objects.create(
            name=f"Foreign {uuid.uuid4().hex[:8]}",
            slug=f"foreign-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self._auth()
        resp = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
            HTTP_X_TENANT_ID=str(other_tenant.id),
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.content

    def test_db_api_key_matching_tenant_header_allowed(self):
        """Control: the key's OWN tenant in X-Tenant-ID passes."""
        self._auth()
        resp = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        assert resp.status_code == status.HTTP_201_CREATED, resp.content


class InternalProcessFileScanTest(TransactionTestCase):
    """W1.14 — the internal path enqueues the ClamAV malware scan.

    A REAL TransactionTestCase is required (not just the
    django_db(transaction=True) mark): in this repo's Django-6 pytest
    context the mark still runs TestCase-derived classes atomic-wrapped,
    and transaction.on_commit callbacks never fire under the rollback —
    the scan enqueue is registered exactly that way.
    """

    def setUp(self):
        self.client = APIClient()
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Scan Test Tenant {unique}",
            slug=f"scan-test-tenant-{unique}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"scan-test-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Scan Test Ingestion",
            source_type=SourceType.S3,
            source_config={"bucket": "test-bucket", "prefix": "data/"},
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}")

    def test_internal_file_enqueues_malware_scan(self):
        from hub.apps.files.models import File, FileScanStatus

        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-ingestions/internal/runs/",
            {"scheduled_ingestion_id": str(self.scheduled_ingestion.id)},
            format="json",
        )
        assert r_create.status_code == status.HTTP_201_CREATED, r_create.content
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
        assert response.status_code == status.HTTP_201_CREATED, response.content
        file_obj = File.objects.get(id=response.data["file_id"])
        # W1.14 contract: the eager scan (RQ ASYNC=False) must have RUN
        # and recorded a TERMINAL outcome instead of leaving the file
        # PENDING forever.  The outcome follows the environment (the
        # W16 policy — probe, don't hardcode): ClamAV reachable → CLEAN
        # (the benign CSV scans clean); unreachable → SCAN_UNAVAILABLE
        # with its audit.
        from hub.apps.files.scanner import ClamAVScanner

        scanner = ClamAVScanner()
        clamav_reachable = False
        try:
            outcome, _threat = scanner.classify_bytes_with_detail(
                b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
            )
            clamav_reachable = outcome == FileScanStatus.INFECTED
        except Exception:
            clamav_reachable = False

        if clamav_reachable:
            assert file_obj.scan_status == FileScanStatus.CLEAN
        else:
            assert file_obj.scan_status == FileScanStatus.SCAN_UNAVAILABLE
            assert AuditEvent.objects.filter(
                action="FILE_MALWARE_SCAN_UNAVAILABLE",
            ).exists()
        assert file_obj.scanned_at is not None
