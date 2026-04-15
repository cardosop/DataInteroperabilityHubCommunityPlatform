"""
Tests for JWT scope enforcement on asset endpoints (Task 220.3).

Verifies that when ENFORCE_JWT_SCOPES=True:
- DATA_CONSUMER (read-only scopes) gets 403 on POST /api/v1/assets/
- DATA_PROVIDER (read+write scopes) can create assets (not 403)
- Read operations remain accessible to DATA_CONSUMER
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(30),
]


class AssetScopeEnforcementTest(TestCase):
    """Verify JWT scope enforcement on AssetViewSet write operations."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Scope Test {uid}",
            slug=f"scope-test-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # DATA_CONSUMER role — has assets:read but NOT assets:write
        self.consumer_role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_CONSUMER",
            description="Read-only consumer",
        )
        self.consumer = User.objects.create_user(
            email=f"consumer-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(
            user=self.consumer, tenant=self.tenant, role=self.consumer_role,
        )

        # DATA_PROVIDER role — has assets:read AND assets:write
        self.provider_role = Role.objects.create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            description="Can publish data",
        )
        self.provider = User.objects.create_user(
            email=f"provider-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(
            user=self.provider, tenant=self.tenant, role=self.provider_role,
        )

        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(user=self.consumer)

        self.provider_client = APIClient()
        self.provider_client.force_authenticate(user=self.provider)

        self.asset_payload = {
            "key": f"test-asset-{uid}",
            "name": f"Test Asset {uid}",
        }
        self.tenant_header = {"HTTP_X_TENANT_ID": str(self.tenant.id)}

    # ---- Write operations (POST) ----

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_consumer_cannot_create_asset(self):
        """DATA_CONSUMER must get 403 on POST /api/v1/assets/ when scopes enforced."""
        resp = self.consumer_client.post(
            "/api/v1/assets/",
            self.asset_payload,
            format="json",
            **self.tenant_header,
        )
        self.assertEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            f"Expected 403, got {resp.status_code}: {resp.data}",
        )

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_provider_can_create_asset(self):
        """DATA_PROVIDER must NOT get 403 on POST /api/v1/assets/ when scopes enforced."""
        resp = self.provider_client.post(
            "/api/v1/assets/",
            self.asset_payload,
            format="json",
            **self.tenant_header,
        )
        # Should succeed (201) or fail for non-permission reasons (400 validation).
        # The key assertion: it must NOT be 403.
        self.assertNotEqual(
            resp.status_code,
            status.HTTP_403_FORBIDDEN,
            f"DATA_PROVIDER should not be denied by scope check: {resp.data}",
        )

    # ---- Write operations (PUT/PATCH/DELETE) ----

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_consumer_cannot_update_asset(self):
        """DATA_CONSUMER must get 403 on PATCH /api/v1/assets/<id>/ when scopes enforced."""
        # Create an asset as provider first
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            key=f"upd-test-{uuid.uuid4().hex[:8]}",
            name="Update Test",
            tenant=self.tenant,
            created_by=self.provider,
        )
        resp = self.consumer_client.patch(
            f"/api/v1/assets/{asset.id}/",
            {"name": "Hacked Name", "version": asset.version},
            format="json",
            **self.tenant_header,
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_consumer_cannot_delete_asset(self):
        """DATA_CONSUMER must get 403 on DELETE /api/v1/assets/<id>/ when scopes enforced."""
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            key=f"del-test-{uuid.uuid4().hex[:8]}",
            name="Delete Test",
            tenant=self.tenant,
            created_by=self.provider,
        )
        resp = self.consumer_client.delete(
            f"/api/v1/assets/{asset.id}/",
            **self.tenant_header,
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ---- Custom @action write operations ----

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_consumer_cannot_attach_dataset(self):
        """DATA_CONSUMER must get 403 on POST @action endpoints (not just CRUD)."""
        from hub.apps.assets.models import Asset

        asset = Asset.objects.create(
            key=f"action-test-{uuid.uuid4().hex[:8]}",
            name="Action Test",
            tenant=self.tenant,
            created_by=self.provider,
        )
        resp = self.consumer_client.post(
            f"/api/v1/assets/{asset.id}/datasets/",
            {"dataset_id": str(uuid.uuid4())},
            format="json",
            **self.tenant_header,
        )
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    # ---- Read operations (GET) ----

    @override_settings(ENFORCE_JWT_SCOPES=True)
    def test_data_consumer_can_list_assets(self):
        """DATA_CONSUMER must still be able to GET /api/v1/assets/ (read is allowed)."""
        resp = self.consumer_client.get(
            "/api/v1/assets/",
            **self.tenant_header,
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    # ---- Legacy mode (flag off) ----

    @override_settings(ENFORCE_JWT_SCOPES=False)
    def test_data_consumer_allowed_when_flag_off(self):
        """Legacy mode: DATA_CONSUMER can create assets when enforcement is off."""
        resp = self.consumer_client.post(
            "/api/v1/assets/",
            self.asset_payload,
            format="json",
            **self.tenant_header,
        )
        # Should NOT be 403 (legacy permissive mode)
        self.assertNotEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
