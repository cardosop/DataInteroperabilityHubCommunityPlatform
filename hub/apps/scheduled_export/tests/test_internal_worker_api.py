"""
Tests for Internal Worker API (run lifecycle, process-export, config, auth).

No mocks: real DB, real ScheduledExportRun, real services (ScheduledExportService, BusinessRules, etc.).
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.timeout(600),
]


def _create_worker_api_key(tenant, user):
    plaintext = APIKey.generate_key()
    key_hash = APIKey.hash_key(plaintext)
    APIKey.objects.create(
        tenant=tenant,
        user=user,
        key_hash=key_hash,
        name="Worker API Key",
        scopes=[SCOPE_SCHEDULED_EXPORT_INTERNAL],
    )
    return plaintext


class InternalWorkerAPITest(TransactionTestCase):
    """
    All Internal Worker API tests in one TransactionTestCase to reduce DB flushes.

    Covers: run lifecycle, auth, config masking, process-export.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for internal API tests."""
        pass

    def setUp(self):
        self.client = APIClient()
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Worker Test Tenant {unique_id}",
            slug=f"worker-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"worker-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)

        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes (POST/PATCH)
        ensure_tenant_has_active_subscription(self.tenant)

        # Create test assets, datasets, files for export scope
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status="ACTIVE",
            visibility="PUBLIC",
            dq_status="PASSED",
            compliance_status="COMPLIANT",
            version=1,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test-file.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"columns": ["id", "name"]},
            created_by=self.user,
        )

        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Worker Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "prefix": "exports/",
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={
                "asset_ids": [str(self.asset.id)],
                "dataset_ids": [str(self.dataset.id)],
                "file_ids": [str(self.file.id)],
            },
        )

        self.config_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Config Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "secret-bucket",
                "secret_access_key": "very-secret-key-value",
                "access_key_id": "AKIA_SECRET_ID",
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}")

    # --- Run lifecycle ---

    def test_create_run_201(self):
        """POST internal/runs/ creates ScheduledExportRun with status RUNNING."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], "RUNNING")
        run = ScheduledExportRun.objects.get(id=response.data["id"])
        self.assertEqual(run.scheduled_export_id, self.scheduled_export.id)
        self.assertEqual(run.tenant_id, self.tenant.id)
        self.assertEqual(run.status, ScheduledExportRunStatus.RUNNING)
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="CREATED",
            resource_id=str(run.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_create_run_idempotency_prefect_flow_run_id(self):
        """Same prefect_flow_run_id returns 200 with existing run."""
        self._auth()
        payload = {
            "scheduled_export_id": str(self.scheduled_export.id),
            "prefect_flow_run_id": "pf-run-123",
        }
        r1 = self.client.post("/api/v1/scheduled-exports/internal/runs/", payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        run_id = r1.data["id"]
        r2 = self.client.post("/api/v1/scheduled-exports/internal/runs/", payload, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["id"], run_id)
        self.assertEqual(
            ScheduledExportRun.objects.filter(scheduled_export=self.scheduled_export).count(),
            1,
        )

    def test_create_run_idempotency_key(self):
        """Same idempotency_key returns 200 with existing run."""
        self._auth()
        payload = {
            "scheduled_export_id": str(self.scheduled_export.id),
            "idempotency_key": "idempotent-key-123",
        }
        r1 = self.client.post("/api/v1/scheduled-exports/internal/runs/", payload, format="json")
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        run_id = r1.data["id"]
        r2 = self.client.post("/api/v1/scheduled-exports/internal/runs/", payload, format="json")
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(r2.data["id"], run_id)

    def test_patch_run_completed(self):
        """PATCH run to COMPLETED updates last_run_at and last_run_status."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        run_id = r_create.data["id"]
        run = ScheduledExportRun.objects.get(id=run_id)
        run.items_found = 10
        run.items_exported = 10
        run.items_failed = 0
        run.save()

        response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {
                "status": "COMPLETED",
                "completed_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.scheduled_export.refresh_from_db()
        self.assertIsNotNone(self.scheduled_export.last_run_at)
        self.assertEqual(self.scheduled_export.last_run_status, ScheduledExportRunStatus.COMPLETED)

        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="UPDATED",
            resource_id=str(run_id),
        ).first()
        self.assertIsNotNone(audit)

    def test_patch_run_update_items(self):
        """PATCH run updates items_found, items_exported, items_failed."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {
                "items_found": 100,
                "items_exported": 95,
                "items_failed": 5,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        run = ScheduledExportRun.objects.get(id=run_id)
        self.assertEqual(run.items_found, 100)
        self.assertEqual(run.items_exported, 95)
        self.assertEqual(run.items_failed, 5)

    # --- Auth ---

    def test_reject_missing_token(self):
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_reject_invalid_token(self):
        self.client.credentials(HTTP_AUTHORIZATION="ApiKey invalid-key-12345")
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

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
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_wrong_tenant(self):
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {unique_id}",
            slug=f"other-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        other_export = ScheduledExport.objects.create(
            tenant=other_tenant,
            name="Other Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "other-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
        )
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(other_export.id)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # --- Config endpoint ---

    def test_get_config_masks_credentials(self):
        """GET config/{id}/ returns config with masked credentials."""
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-exports/internal/config/{self.config_export.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["destination_type"], "S3")
        dest_config = response.data["destination_config"]
        # Credentials should be masked
        self.assertIn("secret_access_key", dest_config)
        self.assertTrue(dest_config["secret_access_key"].endswith("***"))
        self.assertNotEqual(dest_config["secret_access_key"], "very-secret-key-value")
        # Non-sensitive fields should be present
        self.assertEqual(dest_config["bucket"], "secret-bucket")

    def test_get_config_includes_source_scope(self):
        """GET config/{id}/ includes source_scope."""
        self._auth()
        response = self.client.get(
            f"/api/v1/scheduled-exports/internal/config/{self.scheduled_export.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("source_scope", response.data)
        self.assertIn("asset_ids", response.data["source_scope"])
        self.assertIn("dataset_ids", response.data["source_scope"])
        self.assertIn("file_ids", response.data["source_scope"])

    # --- Process-export endpoint ---

    def test_process_export_dataset_success(self):
        """POST process-export/ with dataset_id returns upload instructions."""
        self._auth()
        # Create run first
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        # Process export
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "dataset_id": str(self.dataset.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["item_type"], "dataset")
        self.assertEqual(response.data["item_id"], str(self.dataset.id))
        self.assertIn("upload_url", response.data)
        self.assertIn("upload_method", response.data)

        # Check audit event
        audit = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_ITEM",
            action="PROCESSED",
            resource_id=str(self.dataset.id),
        ).first()
        self.assertIsNotNone(audit)

    def test_process_export_file_success(self):
        """POST process-export/ with file_id returns upload instructions."""
        self._auth()
        # Create run first
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        # Process export
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "file_id": str(self.file.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["item_type"], "file")
        self.assertEqual(response.data["item_id"], str(self.file.id))
        self.assertIn("upload_url", response.data)

    def test_process_export_item_not_in_scope(self):
        """POST process-export/ rejects item not in source_scope."""
        self._auth()
        # Create export with limited scope
        import uuid

        limited_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Limited Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},  # Different asset
        )

        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(limited_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        # Try to export dataset not in scope
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "dataset_id": str(self.dataset.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "ITEM_NOT_IN_SCOPE")

    def test_process_export_requires_item(self):
        """POST process-export/ requires either dataset_id or file_id."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {"run_id": run_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_process_export_rejects_both_items(self):
        """POST process-export/ rejects when both dataset_id and file_id provided."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "dataset_id": str(self.dataset.id),
                "file_id": str(self.file.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "MULTIPLE_ITEMS")

    def test_process_export_invalid_run(self):
        """POST process-export/ rejects invalid run_id."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": str(uuid.uuid4()),
                "dataset_id": str(self.dataset.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_process_export_inactive_export(self):
        """POST process-export/ rejects when scheduled export is not ACTIVE."""
        self._auth()
        paused_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Paused Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"dataset_ids": [str(self.dataset.id)]},
            status=ScheduledExportStatus.PAUSED,
        )

        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(paused_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]

        response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "dataset_id": str(self.dataset.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "EXPORT_NOT_ACTIVE")

    # --- Edge cases and error handling ---

    def test_get_config_nonexistent_export_returns_404(self):
        """GET config/{id}/ for non-existent export returns 404."""
        self._auth()
        url = f"/api/v1/scheduled-exports/internal/config/{uuid.uuid4()}/"
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patch_run_nonexistent_run_returns_404(self):
        """PATCH run with non-existent run_id returns 404."""
        self._auth()
        response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{uuid.uuid4()}/",
            {"status": "COMPLETED"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_run_missing_scheduled_export_id_returns_400(self):
        """POST internal/runs/ without scheduled_export_id returns 400."""
        self._auth()
        response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_patch_run_invalid_completed_at_ignored_or_400(self):
        """PATCH run with invalid completed_at returns 200 (ignored) or 400."""
        self._auth()
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
        )
        run_id = r_create.data["id"]
        response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {"completed_at": "not-a-date"},
            format="json",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST),
        )


class InternalWorkerAPIIntegrationTest(TransactionTestCase):
    """
    Integration tests for scheduled export workflow.

    Tests complete flow: create ScheduledExport → create run → process export → assert results.
    """

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""
        pass

    def setUp(self):
        self.client = APIClient()
        import uuid

        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Integration Test Tenant {unique_id}",
            slug=f"integration-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"integration-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.plaintext_key = _create_worker_api_key(self.tenant, self.user)

        # Ensure tenant has active subscription so TenantSuspensionMiddleware allows writes
        ensure_tenant_has_active_subscription(self.tenant)

        # Create test data
        self.file = File.objects.create(
            tenant=self.tenant,
            name="export-test-file.csv",
            size=2048,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"columns": ["id", "name"]},
            created_by=self.user,
        )

        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Integration Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "export-bucket",
                "prefix": "exports/",
            },
            schedule_config={"cron": "0 2 * * *", "timezone": "UTC"},
            source_scope={
                "dataset_ids": [str(self.dataset.id)],
            },
        )

    def _auth(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_key}")

    def test_complete_export_workflow(self):
        """Integration test: create export → create run → process export → update run."""
        self._auth()

        # 1. Create run
        create_response = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {
                "scheduled_export_id": str(self.scheduled_export.id),
                "prefect_flow_run_id": "pf-integration-test-123",
            },
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        run_id = create_response.data["id"]

        # 2. Process export for dataset
        process_response = self.client.post(
            "/api/v1/scheduled-exports/internal/process-export/",
            {
                "run_id": run_id,
                "dataset_id": str(self.dataset.id),
                "destination_path": "exports/dataset-export.csv",
            },
            format="json",
        )
        self.assertEqual(process_response.status_code, status.HTTP_200_OK)
        self.assertTrue(process_response.data["success"])
        self.assertIn("upload_url", process_response.data)

        # 3. Update run with results
        update_response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {
                "items_found": 1,
                "items_exported": 1,
                "items_failed": 0,
                "status": "COMPLETED",
                "completed_at": timezone.now().isoformat(),
                "result_json": {
                    "items_exported": [
                        {
                            "item_id": str(self.dataset.id),
                            "item_type": "dataset",
                            "destination_path": "exports/dataset-export.csv",
                        }
                    ]
                },
            },
            format="json",
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["status"], "COMPLETED")
        self.assertEqual(update_response.data["items_exported"], 1)

        # 4. Verify scheduled export was updated
        self.scheduled_export.refresh_from_db()
        self.assertIsNotNone(self.scheduled_export.last_run_at)
        self.assertEqual(self.scheduled_export.last_run_status, ScheduledExportRunStatus.COMPLETED)

        # 5. Verify audit events
        audit_events = AuditEvent.objects.filter(
            tenant_id=self.tenant.id,
            resource_type__in=["SCHEDULED_EXPORT_RUN", "SCHEDULED_EXPORT_ITEM"],
        )
        self.assertGreaterEqual(audit_events.count(), 3)  # CREATED, PROCESSED, UPDATED

    def test_config_endpoint_no_credentials(self):
        """Integration test: config endpoint does not expose raw credentials."""
        self._auth()

        # Create export with credentials
        export_with_creds = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Credential Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "secret-bucket",
                "secret_access_key": "AKIAIOSFODNN7EXAMPLE",
                "access_key_id": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"dataset_ids": [str(self.dataset.id)]},
        )

        # Get config
        response = self.client.get(
            f"/api/v1/scheduled-exports/internal/config/{export_with_creds.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify credentials are masked
        dest_config = response.data["destination_config"]
        self.assertIn("secret_access_key", dest_config)
        self.assertTrue(dest_config["secret_access_key"].endswith("***"))
        self.assertNotEqual(dest_config["secret_access_key"], "AKIAIOSFODNN7EXAMPLE")
        self.assertNotEqual(
            dest_config["access_key_id"], "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        )

        # Verify non-sensitive fields are present
        self.assertEqual(dest_config["bucket"], "secret-bucket")
