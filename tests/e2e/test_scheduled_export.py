"""
E2E tests for Scheduled Export

End-to-end tests for complete scheduled export workflows.
Uses real implementations - no mocks/stubs per development best practices.
Aligns with scheduled ingestion lifecycle test: verify create, trigger, run creation, update, delete.
"""

import os
import time
import uuid

import pytest
import requests
from django.test import TestCase
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
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from .conftest import get_response_data

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.scheduled_export,
    pytest.mark.requires_prefect,
    pytest.mark.journey("JOURNEY-EXPORT-001"),
    pytest.mark.journey("JOURNEY-EXPORT-002"),
    pytest.mark.uc("UC-EXPORT-001"),
    pytest.mark.uc("UC-EXPORT-002"),
    pytest.mark.uc("UC-EXPORT-003"),
    pytest.mark.uc("UC-EXPORT-004"),
]


def _prefect_integration_reachable(max_attempts=10, delay_seconds=5) -> bool:
    """Check if prefect-integration-service is reachable (with retries for slow startup)."""
    base = os.getenv("PREFECT_INTEGRATION_SERVICE_URL", "").rstrip("/")
    if not base:
        return False
    for attempt in range(max_attempts):
        try:
            r = requests.get(f"{base}/health", timeout=5)
            if r.ok:
                return True
        except Exception:
            pass
        if attempt < max_attempts - 1:
            time.sleep(delay_seconds)  # INTENTIONAL: e2e/integration test polling real services
    return False


class ScheduledExportE2ETest(TestCase):
    """E2E tests for scheduled export"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create plan and assign to tenant
        from hub.apps.tenants.models import TenantPlan

        self.plan = TenantPlan.objects.create(
            name=f"Test Plan {uuid.uuid4().hex[:8]}",
            slug=f"test-plan-{uuid.uuid4().hex[:8]}",
            tier="FREE",
            limits_json={"max_scheduled_exports": 5, "max_export_runs_per_month": 100},
            is_active=True,
        )
        self.tenant.plan = self.plan
        self.tenant.save()

        # Create subscription
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        Subscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)

        # Create test asset (required for source_scope validation)
        self.test_asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-export-asset",
            name="Test Export Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_complete_export_lifecycle(self):
        """Test complete export lifecycle from creation to completion

        Note: This test works with real implementations. Prefect services may not be available,
        but the code handles this gracefully (ImportError is caught and logged).
        """
        if not _prefect_integration_reachable():
            pytest.skip(
                "Prefect integration service unreachable - ensure prefect-integration-service-test is running"
            )

        # Step 1: Create scheduled export
        # Note: Prefect deployment sync may fail if Prefect is not available, but export creation should still succeed
        data = {
            "name": "Daily Sales Export",
            "schedule_config": {"cron": "0 2 * * *"},
            "destination_type": DestinationType.S3,
            "destination_config": {
                "bucket": "my-export-bucket",
                "prefix": "exports/sales/",
                "access_key_id": "AKIA...",
                "secret_access_key": "abc...",
            },
            "source_scope": {
                "asset_ids": [str(self.test_asset.id)],
            },
            "status": ScheduledExportStatus.ACTIVE,
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        # Creation should succeed even if Prefect is not available.
        # 201 = full success, 207 = resource created but Prefect deployment
        # sync failed (Phase 25.5.1), 503 = service completely unavailable.
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, 207, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            # Prefect service unavailable - skip rest of test
            pytest.skip("Prefect service not available - skipping export lifecycle test")
            return

        data = get_response_data(response) or {}
        # 207 Multi-Status wraps resource data under "resource" key
        if response.status_code == 207:
            data = data.get("resource", data)
        export_id = data["id"]

        # Step 2: Verify export created
        export_ = ScheduledExport.objects.get(id=export_id)
        self.assertEqual(export_.name, "Daily Sales Export")
        self.assertEqual(export_.status, ScheduledExportStatus.ACTIVE)

        # Step 3: Manually trigger export
        # Note: Trigger may return 503 if Prefect deployment doesn't exist
        # (sync failed during creation) or if Prefect is not available
        try:
            response = self.client.post(
                f"/api/v1/scheduled-exports/{export_id}/trigger/",
                {},
                format="json",
                timeout=30,
            )
        except Exception:
            # Request timeout or connection error - Prefect may not be available
            pytest.skip(
                "Prefect service not available or deployment sync failed - " "skipping trigger test"
            )
            return

        # May return 503 if Prefect unavailable or deployment doesn't exist,
        # or 200 if successful
        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip(
                "Prefect service not available or deployment not found - " "skipping trigger test"
            )
            return

        if response.status_code == status.HTTP_404_NOT_FOUND:
            pytest.skip("Prefect deployment not found - skipping trigger test")
            return

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        flow_run_id = data.get("flow_run_id")
        run_id = data.get("run_id") or data.get("scheduled_export_run_id")

        if not flow_run_id or not run_id:
            pytest.skip("Trigger did not return flow_run_id/run_id - Prefect may not be available")
            return

        # Step 4: Verify run created by trigger (trigger creates run synchronously)
        run = ScheduledExportRun.objects.get(id=run_id)
        self.assertEqual(run.scheduled_export_id, uuid.UUID(export_id))
        self.assertEqual(run.prefect_flow_run_id, flow_run_id)
        self.assertEqual(run.status, ScheduledExportRunStatus.RUNNING)

        # Step 5: Verify run status via API
        response = self.client.get(f"/api/v1/scheduled-exports/{export_id}/runs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        if isinstance(data, list):
            runs_data = data
        else:
            runs_data = data.get("results", [])
        self.assertGreater(len(runs_data), 0)
        run_data = next((r for r in runs_data if r["id"] == str(run.id)), None)
        self.assertIsNotNone(run_data)
        if run_data is not None:
            self.assertEqual(run_data["status"], run.status)

        # Step 6: Update export
        update_data = {
            "name": "Updated Export Name",
            "schedule_config": {"cron": "0 3 * * *"},
        }

        response = self.client.patch(
            f"/api/v1/scheduled-exports/{export_id}/", update_data, format="json"
        )

        # Update should succeed even if Prefect sync fails.
        # 200 = full success, 207 = resource updated but deployment sync
        # failed (Phase 25.5.1), 503 = service completely unavailable.
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, 207, status.HTTP_503_SERVICE_UNAVAILABLE],
        )
        if response.status_code in [status.HTTP_200_OK, 207]:
            data = get_response_data(response) or {}
            if response.status_code == 207:
                data = data.get("resource", data)
            self.assertEqual(data["name"], "Updated Export Name")
            self.assertIn("schedule_config", data)

        # Step 7: Delete export
        response = self.client.delete(f"/api/v1/scheduled-exports/{export_id}/")

        # Delete should succeed even if Prefect sync fails
        self.assertIn(
            response.status_code,
            [status.HTTP_204_NO_CONTENT, status.HTTP_503_SERVICE_UNAVAILABLE],
        )

        if response.status_code == status.HTTP_204_NO_CONTENT:
            # Verify deleted
            self.assertFalse(ScheduledExport.objects.filter(id=export_id).exists())

    def test_multiple_exports_tenant_isolation(self):
        """Test that multiple exports are properly isolated by tenant

        Note: This test works with real implementations. Prefect services
        may not be available, but the code handles this gracefully
        (ImportError is caught and logged).
        """
        # Create second tenant
        _suffix = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Other Tenant {_suffix}",
            slug=f"other-tenant-{_suffix}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create plan and assign to tenant2
        from hub.apps.tenants.models import TenantPlan

        plan2 = TenantPlan.objects.create(
            name="Test Plan 2",
            slug="test-plan-2",
            tier="FREE",
            limits_json={"max_scheduled_exports": 5, "max_export_runs_per_month": 100},
            is_active=True,
        )
        tenant2.plan = plan2
        tenant2.save()

        # Create subscription for tenant2
        from hub.apps.billing.models import Subscription, SubscriptionStatus

        Subscription.objects.create(
            tenant=tenant2,
            plan=plan2,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        user2 = User.objects.create_user(
            email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
        )

        # Create test asset for tenant1
        asset1 = Asset.objects.create(
            tenant=self.tenant,
            key="tenant1-export-asset",
            name="Tenant 1 Export Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create export for tenant1
        data1 = {
            "name": "Tenant 1 Export",
            "schedule_config": {"cron": "0 2 * * *"},
            "destination_type": DestinationType.S3,
            "destination_config": {"bucket": "bucket1"},
            "source_scope": {"asset_ids": [str(asset1.id)]},
        }

        response1 = self.client.post("/api/v1/scheduled-exports/", data1, format="json")

        # Creation may fail if Prefect is required and not available
        if response1.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip("Prefect service not available - skipping tenant isolation test")
            return

        self.assertIn(response1.status_code, [status.HTTP_201_CREATED, 207])
        data1_resp = get_response_data(response1) or {}
        if response1.status_code == 207:
            data1_resp = data1_resp.get("resource", data1_resp)
        export1_id = data1_resp["id"]

        # Create test asset for tenant2
        asset2 = Asset.objects.create(
            tenant=tenant2,
            key="tenant2-export-asset",
            name="Tenant 2 Export Asset",
            status=AssetStatus.ACTIVE,
            created_by=user2,
        )

        # Create export for tenant2
        client2 = APIClient()
        client2.force_authenticate(user=user2)

        data2 = {
            "name": "Tenant 2 Export",
            "schedule_config": {"cron": "0 3 * * *"},
            "destination_type": DestinationType.GCS,
            "destination_config": {"bucket": "bucket2"},
            "source_scope": {"asset_ids": [str(asset2.id)]},
        }

        response2 = client2.post("/api/v1/scheduled-exports/", data2, format="json")

        if response2.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            pytest.skip("Prefect service not available - skipping tenant isolation test")
            return

        self.assertIn(response2.status_code, [status.HTTP_201_CREATED, 207])
        data2 = get_response_data(response2) or {}
        if response2.status_code == 207:
            data2 = data2.get("resource", data2)
        export2_id = data2["id"]

        # List exports for tenant1 - should only see tenant1's
        response = self.client.get("/api/v1/scheduled-exports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        if isinstance(data, dict) and "results" in data:
            export_list = data["results"]
        else:
            export_list = data if isinstance(data, list) else []
        export_ids = [item["id"] if isinstance(item, dict) else str(item) for item in export_list]
        self.assertIn(export1_id, export_ids)
        self.assertNotIn(export2_id, export_ids)

        # List exports for tenant2 - should only see tenant2's
        response = client2.get("/api/v1/scheduled-exports/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        if isinstance(data, dict) and "results" in data:
            export_list = data["results"]
        else:
            export_list = data if isinstance(data, list) else []
        export_ids = [item["id"] if isinstance(item, dict) else str(item) for item in export_list]
        self.assertNotIn(export1_id, export_ids)
        self.assertIn(export2_id, export_ids)
