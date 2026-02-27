"""
Integration tests for run completion side effects.

Tests that PATCH run to COMPLETED/FAILED triggers:
- next_run_at calculation
- cost tracking
- notifications (if configured)
- domain events and audit
"""

import uuid

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.scheduled_export.cost_tracking import CostTrackingManager
from hub.apps.scheduled_export.internal_auth import SCOPE_SCHEDULED_EXPORT_INTERNAL
from hub.apps.scheduled_export.models import (
    DestinationType,
    ExportRunCost,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.worker_run_lifecycle import apply_run_completion_side_effects
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


class RunCompletionSideEffectsIntegrationTest(TransactionTestCase):
    """Integration tests for run completion side effects."""

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests."""
        pass

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Side Effects Test Tenant {unique_id}",
            slug=f"side-effects-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        # Ensure tenant has active subscription before any request (TenantSuspensionMiddleware checks this)
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"side-effects-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.client = APIClient()
        self.worker_key = _create_worker_api_key(self.tenant, self.user)
        # Set credentials for all requests in this test class
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.worker_key}", HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        # Create an asset for the source_scope
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )

        # Create scheduled export
        self.scheduled_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

    def test_patch_run_completed_updates_next_run_at(self):
        """PATCH run to COMPLETED updates next_run_at on scheduled export."""
        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
            items_found=10,
            items_exported=8,
            items_failed=2,
        )

        # Update to COMPLETED
        apply_run_completion_side_effects(run, "COMPLETED")

        # Refresh scheduled export
        self.scheduled_export.refresh_from_db()
        self.assertIsNotNone(self.scheduled_export.next_run_at)
        self.assertEqual(self.scheduled_export.last_run_status, "COMPLETED")
        self.assertIsNotNone(self.scheduled_export.last_run_at)

    def test_patch_run_completed_creates_cost_record(self):
        """PATCH run to COMPLETED creates cost record."""
        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            items_found=10,
            items_exported=8,
            items_failed=2,
            result_json={"items_exported": [{"size_bytes": 1024 * 1024}]},  # 1MB
        )

        # Update to COMPLETED
        apply_run_completion_side_effects(run, "COMPLETED")

        # Verify cost record was created
        cost_exists = ExportRunCost.objects.filter(run=run).exists()
        self.assertTrue(cost_exists, "Cost record should be created on COMPLETED")

        # Verify cost record has components
        cost = ExportRunCost.objects.get(run=run)
        self.assertIsNotNone(cost.cost_components)
        self.assertIn("storage", cost.cost_components)
        self.assertIn("compute", cost.cost_components)
        self.assertIn("network", cost.cost_components)

    def test_patch_run_completed_clears_error_status(self):
        """PATCH run to COMPLETED clears ERROR status on scheduled export."""
        # Set export to ERROR status
        self.scheduled_export.status = ScheduledExportStatus.ERROR
        self.scheduled_export.save()

        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
            items_found=10,
            items_exported=8,
            items_failed=2,
        )

        # Update to COMPLETED
        apply_run_completion_side_effects(run, "COMPLETED")

        # Refresh scheduled export
        self.scheduled_export.refresh_from_db()
        self.assertEqual(self.scheduled_export.status, ScheduledExportStatus.ACTIVE)

    def test_patch_run_failed_sets_error_status(self):
        """PATCH run to FAILED sets ERROR status on scheduled export."""
        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.scheduled_export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
            items_found=10,
            items_exported=0,
            items_failed=10,
            result_json={"error_message": "Export failed"},
        )

        # Update to FAILED
        apply_run_completion_side_effects(run, "FAILED")

        # Refresh scheduled export
        self.scheduled_export.refresh_from_db()
        self.assertEqual(self.scheduled_export.status, ScheduledExportStatus.ERROR)
        self.assertEqual(self.scheduled_export.last_run_status, "FAILED")

    def test_patch_run_completed_via_api_triggers_side_effects(self):
        """PATCH run to COMPLETED via API triggers all side effects."""
        # Ensure authentication is set (credentials are set in setUp, but ensure they're still active)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.worker_key}", HTTP_X_TENANT_ID=str(self.tenant.id)
        )

        # Create run via API
        r_create = self.client.post(
            "/api/v1/scheduled-exports/internal/runs/",
            {"scheduled_export_id": str(self.scheduled_export.id)},
            format="json",
            HTTP_X_TENANT_ID=str(self.tenant.id),
        )
        self.assertEqual(r_create.status_code, status.HTTP_201_CREATED)
        run_id = r_create.data["id"]

        # Update run to COMPLETED via API
        response = self.client.patch(
            f"/api/v1/scheduled-exports/internal/runs/{run_id}/",
            {
                "status": "COMPLETED",
                "items_found": 10,
                "items_exported": 8,
                "items_failed": 2,
                "completed_at": timezone.now().isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify side effects
        self.scheduled_export.refresh_from_db()
        self.assertIsNotNone(self.scheduled_export.next_run_at)
        self.assertEqual(self.scheduled_export.last_run_status, "COMPLETED")

        # Verify cost record was created
        run = ScheduledExportRun.objects.get(id=run_id)
        cost_exists = ExportRunCost.objects.filter(run=run).exists()
        self.assertTrue(cost_exists, "Cost record should be created on COMPLETED")

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT_RUN",
            action="UPDATED",
            resource_id=run_id,
        )
        self.assertEqual(audit_events.count(), 1)
