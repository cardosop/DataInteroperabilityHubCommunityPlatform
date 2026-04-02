"""
Unit tests for Scheduled Export API views

Tests for CRUD operations, run history, and manual trigger endpoints with tenant isolation.
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.uc("UC-EXPORT-001"),
    pytest.mark.uc("UC-EXPORT-002"),
    pytest.mark.uc("UC-EXPORT-003"),
    pytest.mark.uc("UC-EXPORT-004"),
]


def _scheduled_export_kwargs(tenant, **overrides):
    """Minimum required kwargs for ScheduledExport.objects.create"""
    # Create a test asset if not provided
    if "source_scope" not in overrides:
        import uuid

        from hub.apps.assets.models import Asset, AssetStatus

        unique_id = uuid.uuid4().hex[:8]
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"test-asset-{unique_id}",  # Unique key required per tenant
            name=f"Test Asset {unique_id}",
            status=AssetStatus.ACTIVE,
        )
        source_scope = {"asset_ids": [str(asset.id)]}
    else:
        source_scope = overrides.pop("source_scope", {"asset_ids": []})

    kwargs = {
        "tenant": tenant,
        "name": overrides.get("name", "Test Export"),
        "schedule_config": {"cron": "0 0 * * *", "timezone": "UTC"},
        "destination_type": DestinationType.S3,
        "destination_config": {"bucket": "test-bucket", "prefix": "exports/"},
        "source_scope": source_scope,
        "status": ScheduledExportStatus.ACTIVE,
    }
    kwargs.update(overrides)
    return kwargs


class ScheduledExportViewSetTest(TestCase):
    """Test ScheduledExportViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        ensure_tenant_has_active_subscription(self.tenant)

        self.client.force_authenticate(user=self.user)

    def test_create_scheduled_export(self):
        """Test creating a scheduled export"""
        # Create a test asset for source_scope
        import uuid

        from hub.apps.assets.models import Asset, AssetStatus

        unique_id = uuid.uuid4().hex[:8]
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_id}",  # Unique key required per tenant
            name="Test Asset",
            status=AssetStatus.ACTIVE,
        )

        data = {
            "name": "Daily Sales Export",
            "schedule_config": {"cron": "0 2 * * *", "timezone": "UTC"},
            "destination_type": DestinationType.S3,
            "destination_config": {
                "bucket": "my-data-lake",
                "prefix": "exports/sales/",
                "access_key_id": "AKIA...",
                "secret_access_key": "abc...",
            },
            "source_scope": {"asset_ids": [str(asset.id)]},
            "status": ScheduledExportStatus.ACTIVE,
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        # 201 = created with successful Prefect sync
        # 207 = created but Prefect deployment sync failed (expected in test env)
        self.assertIn(response.status_code, (status.HTTP_201_CREATED, 207))
        resp_data = response.data
        # 207 wraps the resource inside a "resource" key
        if response.status_code == 207:
            resp_data = response.data.get("resource", response.data)
        self.assertEqual(resp_data["name"], "Daily Sales Export")
        self.assertEqual(resp_data["destination_type"], DestinationType.S3)
        self.assertIn("id", resp_data)

        export = ScheduledExport.objects.get(id=resp_data["id"])
        self.assertEqual(export.tenant, self.tenant)

    def test_create_scheduled_export_invalid_cron(self):
        """Test creating a scheduled export with invalid cron expression"""
        data = {
            "name": "Invalid Export",
            "schedule_config": {"cron": "invalid", "timezone": "UTC"},
            "destination_type": DestinationType.S3,
            "destination_config": {"bucket": "test-bucket"},
            "source_scope": {"asset_ids": []},
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cron", str(response.data).lower())

    def test_create_scheduled_export_invalid_source_scope(self):
        """Test creating a scheduled export with invalid source_scope"""
        data = {
            "name": "Invalid Export",
            "schedule_config": {"cron": "0 0 * * *", "timezone": "UTC"},
            "destination_type": DestinationType.S3,
            "destination_config": {"bucket": "test-bucket"},
            "source_scope": {},  # Empty source_scope should fail validation
        }

        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("source_scope", str(response.data).lower())

    def test_list_scheduled_exports(self):
        """Test listing scheduled exports"""
        export1 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Export 1")
        )
        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Export 2")
        )

        response = self.client.get("/api/v1/scheduled-exports/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        export_ids = [item["id"] for item in results]
        self.assertIn(str(export1.id), export_ids)
        self.assertIn(str(export2.id), export_ids)

    def test_retrieve_scheduled_export(self):
        """Test retrieving a specific scheduled export"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Test Export")
        )

        response = self.client.get(f"/api/v1/scheduled-exports/{export.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(export.id))
        self.assertEqual(response.data["name"], "Test Export")

    def test_update_scheduled_export(self):
        """Test updating a scheduled export"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Original Name")
        )

        data = {"name": "Updated Name"}

        response = self.client.patch(f"/api/v1/scheduled-exports/{export.id}/", data, format="json")

        # 200 = updated with successful Prefect sync
        # 207 = updated but Prefect deployment sync failed (expected in test env)
        self.assertIn(response.status_code, (status.HTTP_200_OK, 207))
        resp_data = response.data
        if response.status_code == 207:
            resp_data = response.data.get("resource", response.data)
        self.assertEqual(resp_data["name"], "Updated Name")

        export.refresh_from_db()
        self.assertEqual(export.name, "Updated Name")

    def test_delete_scheduled_export(self):
        """Test deleting a scheduled export"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="To Delete")
        )

        response = self.client.delete(f"/api/v1/scheduled-exports/{export.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(ScheduledExport.objects.filter(id=export.id).exists())

    def test_list_runs(self):
        """Test listing runs for a scheduled export"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Test Export")
        )

        run1 = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1),
        )
        run2 = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now() - timedelta(minutes=30),
        )

        response = self.client.get(f"/api/v1/scheduled-exports/{export.id}/runs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        run_ids = [item["id"] for item in response.data]
        self.assertIn(str(run1.id), run_ids)
        self.assertIn(str(run2.id), run_ids)

    def test_retrieve_run(self):
        """Test retrieving a specific run"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Test Export")
        )

        run = ScheduledExportRun.objects.create(
            scheduled_export=export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now(),
            result_json={"items_exported": 5},
        )

        # Retrieve run via flat runs endpoint: /api/v1/scheduled-exports/runs/{run_id}/
        response = self.client.get(f"/api/v1/scheduled-exports/runs/{run.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["id"], str(run.id))
        self.assertEqual(response.data["result_json"]["items_exported"], 5)

    def test_trigger_export_not_active(self):
        """Test triggering a non-active scheduled export"""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(
                self.tenant, name="Test Export", status=ScheduledExportStatus.PAUSED
            )
        )
        response = self.client.post(f"/api/v1/scheduled-exports/{export.id}/trigger/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("not active", response.data.get("error", "").lower())

    def test_tenant_isolation(self):
        """Test that tenants can only see their own scheduled exports"""
        _uid = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(
                tenant2, name="Other Export", destination_config={"bucket": "other-bucket"}
            )
        )

        response = self.client.get("/api/v1/scheduled-exports/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        export_ids = [item["id"] for item in results]
        self.assertNotIn(str(export2.id), export_ids)

    def test_tenant_isolation_retrieve(self):
        """Test that tenants cannot retrieve other tenants' scheduled exports"""
        _uid = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(tenant2, name="Other Export")
        )

        response = self.client.get(f"/api/v1/scheduled-exports/{export2.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_tenant_isolation_runs(self):
        """Test that tenants can only see runs for their own scheduled exports"""
        _uid = uuid.uuid4().hex[:8]
        tenant2 = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(tenant2, name="Other Export")
        )

        run2 = ScheduledExportRun.objects.create(
            scheduled_export=export2,
            tenant=tenant2,
            status=ScheduledExportRunStatus.COMPLETED,
        )

        # Try to retrieve run from other tenant
        response = self.client.get(f"/api/v1/scheduled-exports/runs/{run2.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_filter_by_status(self):
        """Test filtering scheduled exports by status"""
        export1 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(
                self.tenant, name="Active Export", status=ScheduledExportStatus.ACTIVE
            )
        )
        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(
                self.tenant, name="Paused Export", status=ScheduledExportStatus.PAUSED
            )
        )

        response = self.client.get("/api/v1/scheduled-exports/?status=ACTIVE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = (
            response.data.get("results", response.data)
            if isinstance(response.data, dict)
            else response.data
        )
        export_ids = [item["id"] for item in results]
        self.assertIn(str(export1.id), export_ids)
        self.assertNotIn(str(export2.id), export_ids)

    # --- Edge cases ---

    def test_retrieve_invalid_uuid_returns_404(self):
        """Retrieve with non-existent UUID returns 404."""
        response = self.client.get(
            "/api/v1/scheduled-exports/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_malformed_uuid_returns_404(self):
        """Retrieve with malformed ID returns 404."""
        response = self.client.get("/api/v1/scheduled-exports/not-a-uuid/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_list_unauthenticated_returns_401(self):
        """List without authentication returns 401."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/scheduled-exports/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_unauthenticated_returns_401(self):
        """Create without authentication returns 401."""
        self.client.force_authenticate(user=None)
        data = {
            "name": "Unauth Export",
            "schedule_config": {"cron": "0 0 * * *", "timezone": "UTC"},
            "destination_type": DestinationType.S3,
            "destination_config": {"bucket": "b"},
            "source_scope": {"asset_ids": []},
        }
        response = self.client.post("/api/v1/scheduled-exports/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_with_invalid_destination_config_returns_400(self):
        """Update with invalid destination_config (e.g. missing bucket for S3) returns 400."""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="To Update")
        )
        data = {"destination_config": {}}
        response = self.client.patch(f"/api/v1/scheduled-exports/{export.id}/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Verify error response references the validation issue
        resp_str = str(response.data).lower()
        self.assertTrue(
            "destination" in resp_str or "bucket" in resp_str
            or "code" in response.data,
            f"Error response should reference destination/bucket "
            f"validation, got: {response.data}",
        )

    def test_delete_other_tenant_export_returns_404(self):
        """Delete called for another tenant's export returns 404 (get_object filters by tenant)."""
        tenant2 = Tenant.objects.create(
            name="Other Tenant 2",
            slug="other-tenant-2",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        export2 = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(tenant2, name="Other Export")
        )
        response = self.client.delete(f"/api/v1/scheduled-exports/{export2.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_trigger_with_malformed_body_returns_400(self):
        """Trigger with invalid JSON body returns 400."""
        export = ScheduledExport.objects.create(
            **_scheduled_export_kwargs(self.tenant, name="Trigger Export")
        )
        response = self.client.post(
            f"/api/v1/scheduled-exports/{export.id}/trigger/",
            "not json",
            content_type="text/plain",
        )
        self.assertIn(
            response.status_code,
            (status.HTTP_400_BAD_REQUEST, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE),
        )
