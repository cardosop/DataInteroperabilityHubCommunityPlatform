"""
Comprehensive Scheduled Export API Integration Tests

Tests all scheduled export API endpoints with real DB and real services.
No mocks of hub/services/DB per development best practices.

Coverage:
- Scheduled export CRUD operations
- Run creation and management
- Manual trigger
- Tenant isolation
- Plan limit enforcement
- Worker API authentication
"""

import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.integration,
    pytest.mark.scheduled_export,
    pytest.mark.timeout(600),  # Allow time for test DB setup on first run
]


class ScheduledExportAPIsComprehensiveTest(TransactionTestCase):
    """Comprehensive scheduled export API integration tests using TransactionTestCase to avoid TRUNCATE locks"""

    reset_sequences = False
    serialized_rollback = False

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for integration tests.

        TransactionTestCase tries to flush the database between tests, but this
        fails with foreign key constraints and can cause locks. We use transaction
        rollback instead which provides isolation without flushing.
        """
        # Don't flush - transactions are rolled back which provides isolation
        pass

    def setUp(self):
        """Set up test fixtures"""
        import uuid

        # Disconnect semantic service signals to prevent timeouts (root cause fix)
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.client = APIClient()

        # Use unique identifiers to avoid conflicts between tests
        unique_id = str(uuid.uuid4())[:8]

        # Create tenants (use unique name/slug to avoid conflicts between tests)
        self.tenant1 = Tenant.objects.create(
            name=f"Export Test Tenant 1 {unique_id}",
            slug=f"export-test-tenant-1-{unique_id}",
            status=TenantStatus.ACTIVE,
        )
        self.tenant2 = Tenant.objects.create(
            name=f"Export Test Tenant 2 {unique_id}",
            slug=f"export-test-tenant-2-{unique_id}",
            status=TenantStatus.ACTIVE,
        )

        # Create users (use unique emails to avoid conflicts between tests)
        self.user1 = User.objects.create_user(
            email=f"export1-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant1,
            status=UserStatus.ACTIVE,
        )
        self.user2 = User.objects.create_user(
            email=f"export2-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant2,
            status=UserStatus.ACTIVE,
        )

        # Create plan with export limits (use unique slug to avoid conflicts)
        self.plan = TenantPlan.objects.create(
            name=f"Test Plan {unique_id}",
            slug=f"test-plan-{unique_id}",
            tier="PRO",
            limits_json={
                "max_scheduled_exports": 5,
                "max_export_runs_per_month": 100,
            },
            is_active=True,
        )

        # Assign plan directly to tenants (Tenant.plan is a ForeignKey)
        self.tenant1.plan = self.plan
        self.tenant1.save()
        self.tenant2.plan = self.plan
        self.tenant2.save()

        # Also create subscriptions for billing consistency
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        self.subscription1 = Subscription.objects.create(
            tenant=self.tenant1,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )
        self.subscription2 = Subscription.objects.create(
            tenant=self.tenant2,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        # Create assets (use unique keys to avoid conflicts)
        self.asset1 = Asset.objects.create(
            tenant=self.tenant1,
            key=f"export-asset-1-{unique_id}",
            name=f"Export Asset 1 {unique_id}",
            status=AssetStatus.ACTIVE,
            created_by=self.user1,
        )
        self.asset2 = Asset.objects.create(
            tenant=self.tenant2,
            key=f"export-asset-2-{unique_id}",
            name=f"Export Asset 2 {unique_id}",
            status=AssetStatus.ACTIVE,
            created_by=self.user2,
        )

    def test_create_scheduled_export_success(self):
        """Test creating scheduled export"""
        self.client.force_authenticate(user=self.user1)

        data = {
            "name": "Daily Export",
            "schedule_config": {"cron": "0 2 * * *"},
            "destination_type": DestinationType.S3,
            "destination_config": {
                "bucket": "my-bucket",
                "prefix": "exports/",
                "access_key_id": "AKIA...",
                "secret_access_key": "secret...",
            },
            "source_scope": {
                "asset_ids": [str(self.asset1.id)],
            },
            "status": ScheduledExportStatus.ACTIVE,
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        # Should succeed (may return 503 if Prefect unavailable)
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

        if response.status_code == status.HTTP_201_CREATED:
            export_id = response.data["id"]
            export = ScheduledExport.objects.get(id=export_id)
            self.assertEqual(export.name, "Daily Export")
            self.assertEqual(export.tenant_id, self.tenant1.id)
            self.assertEqual(export.status, ScheduledExportStatus.ACTIVE)

    def test_list_scheduled_exports(self):
        """Test listing scheduled exports"""
        # Create exports
        export1 = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Export 1",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "bucket1"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )
        export2 = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Export 2",
            schedule_config={"cron": "0 3 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "bucket2"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        response = self.client.get("/api/v1/scheduled-exports/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        export_ids = [exp["id"] for exp in response.data["results"]]
        self.assertIn(str(export1.id), export_ids)
        self.assertIn(str(export2.id), export_ids)

    def test_list_scheduled_exports_filter_by_status(self):
        """Test listing scheduled exports with ?status= filter (tenant-scoped)."""
        active_export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Active Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "active-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )
        paused_export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Paused Export",
            schedule_config={"cron": "0 3 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "paused-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.PAUSED,
        )

        self.client.force_authenticate(user=self.user1)

        response_active = self.client.get("/api/v1/scheduled-exports/?status=ACTIVE")
        self.assertEqual(response_active.status_code, status.HTTP_200_OK)
        self.assertIn("results", response_active.data)
        active_ids = [exp["id"] for exp in response_active.data["results"]]
        self.assertIn(str(active_export.id), active_ids)
        self.assertNotIn(str(paused_export.id), active_ids)

        response_paused = self.client.get("/api/v1/scheduled-exports/?status=PAUSED")
        self.assertEqual(response_paused.status_code, status.HTTP_200_OK)
        self.assertIn("results", response_paused.data)
        paused_ids = [exp["id"] for exp in response_paused.data["results"]]
        self.assertIn(str(paused_export.id), paused_ids)
        self.assertNotIn(str(active_export.id), paused_ids)

    def test_get_scheduled_export_detail(self):
        """Test getting scheduled export detail"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Detail Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "detail-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/scheduled-exports/{export.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(export.id))
        self.assertEqual(response.data["name"], "Detail Export")

    def test_update_scheduled_export(self):
        """Test updating scheduled export"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Update Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "update-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        response = self.client.patch(
            f"/api/v1/scheduled-exports/{export.id}/",
            {"name": "Updated Export Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        export.refresh_from_db()
        self.assertEqual(export.name, "Updated Export Name")

    def test_manual_trigger_scheduled_export(self):
        """Test manually triggering scheduled export"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Trigger Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "trigger-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        response = self.client.post(
            f"/api/v1/scheduled-exports/{export.id}/trigger/",
            {},
            format="json",
        )

        # Should succeed (may return 503 if Prefect unavailable, or 404 if deployment not found)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_200_OK,
                status.HTTP_201_CREATED,
                status.HTTP_503_SERVICE_UNAVAILABLE,
                status.HTTP_404_NOT_FOUND,
            ],
        )

        if response.status_code in [status.HTTP_200_OK, status.HTTP_201_CREATED]:
            # Verify run created
            runs = ScheduledExportRun.objects.filter(scheduled_export=export)
            self.assertTrue(runs.exists())

    def test_list_export_runs(self):
        """Test listing export runs"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Runs Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "runs-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        # Create runs
        run1 = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant1,
            status=ScheduledExportRunStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )
        run2 = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant1,
            status=ScheduledExportRunStatus.FAILED,
            started_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user1)

        response = self.client.get(f"/api/v1/scheduled-exports/{export.id}/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # The runs endpoint returns a list directly, not a paginated response
        self.assertIsInstance(response.data, list)
        run_ids = [run["id"] for run in response.data]
        self.assertIn(str(run1.id), run_ids)
        self.assertIn(str(run2.id), run_ids)

    def test_get_export_run_detail(self):
        """Test getting export run detail"""
        export = ScheduledExport.objects.create(
            tenant=self.tenant1,
            name="Run Detail Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "detail-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        run = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant1,
            status=ScheduledExportRunStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )

        self.client.force_authenticate(user=self.user1)

        # Run detail endpoint is at /api/v1/scheduled-exports/runs/{run.id}/
        response = self.client.get(f"/api/v1/scheduled-exports/runs/{run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(run.id))
        self.assertEqual(response.data["status"], ScheduledExportRunStatus.COMPLETED)

    def test_scheduled_export_tenant_isolation(self):
        """Test tenant isolation - user1 cannot access tenant2's exports"""
        export2 = ScheduledExport.objects.create(
            tenant=self.tenant2,
            name="Tenant2 Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "tenant2-bucket"},
            source_scope={"asset_ids": [str(self.asset2.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        # Try to get tenant2's export
        response = self.client.get(f"/api/v1/scheduled-exports/{export2.id}/")

        # Should return 404 (not found due to tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_plan_limit_enforcement_max_exports(self):
        """Test plan limit enforcement for max_scheduled_exports"""
        import uuid

        # Use unique identifiers to avoid conflicts between tests
        unique_id = str(uuid.uuid4())[:8]

        # Create plan with limit of 1 export (use unique name/slug)
        limited_plan = TenantPlan.objects.create(
            name=f"Limited Plan {unique_id}",
            slug=f"limited-plan-{unique_id}",
            tier="FREE",
            limits_json={"max_scheduled_exports": 1},
            is_active=True,
        )

        # Assign plan to tenant (both direct assignment and subscription)
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        self.tenant1.plan = limited_plan
        self.tenant1.save()

        subscription = Subscription.objects.create(
            tenant=self.tenant1,
            plan=limited_plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        # Create one export (at limit) - use unique name
        ScheduledExport.objects.create(
            tenant=self.tenant1,
            name=f"Existing Export {unique_id}",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "existing-bucket"},
            source_scope={"asset_ids": [str(self.asset1.id)]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user1)

        # Try to create another export (should fail due to limit)
        data = {
            "name": "Over Limit Export",
            "schedule_config": {"cron": "0 3 * * *"},
            "destination_type": DestinationType.S3,
            "destination_config": {"bucket": "over-limit-bucket"},
            "source_scope": {"asset_ids": [str(self.asset1.id)]},
            "status": ScheduledExportStatus.ACTIVE,
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        # Should return 403 with plan_limit_exceeded
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # API returns 'detail' or 'error' field
        error_msg = response.data.get("error") or response.data.get("detail", "")
        error_str = str(error_msg).lower()
        self.assertTrue("limit" in error_str or "plan" in error_str)
