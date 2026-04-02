"""
Unit tests for Tenant API views.

Uses real User model (no mocks/stubs). Platform admin has tenant=None; regular user has a tenant.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantViewSetTest(TestCase):
    """Test TenantViewSet with real User model."""

    def setUp(self):
        """Set up test fixtures: platform admin (tenant=None) and regular user (with tenant)."""
        self.client = APIClient()
        self.tenant_for_user = Tenant.objects.create(name="User Tenant", slug="user-tenant")
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        uid = uuid.uuid4().hex[:8]
        self.regular_user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_for_user,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_create_tenant(self):
        """Test tenant creation via API"""
        self.client.force_authenticate(user=self.platform_admin)

        _uid = uuid.uuid4().hex[:8]
        response = self.client.post(
            "/api/v1/tenants/",
            {"name": f"New Tenant {_uid}", "slug": f"new-tenant-{_uid}", "region": "us-east-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], f"New Tenant {_uid}")
        self.assertEqual(response.data["slug"], f"new-tenant-{_uid}")
        self.assertEqual(response.data["status"], TenantStatus.ACTIVE)
        self.assertEqual(response.data["kyc_status"], KYCStatus.UNVERIFIED)

    def test_create_tenant_requires_platform_admin(self):
        """Test that only platform admins can create tenants"""
        self.client.force_authenticate(user=self.regular_user)

        _uid = uuid.uuid4().hex[:8]
        response = self.client.post(
            "/api/v1/tenants/",
            {"name": f"New Tenant {_uid}", "slug": f"new-tenant-{_uid}"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_tenant(self):
        """Test tenant retrieval via API"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(f"/api/v1/tenants/{tenant.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], tenant.name)

    def test_update_tenant(self):
        """Test tenant update via API"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.patch(
            f"/api/v1/tenants/{tenant.id}/",
            {"name": "Updated Tenant", "kyc_status": KYCStatus.VERIFIED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Tenant")
        self.assertEqual(response.data["kyc_status"], KYCStatus.VERIFIED)
        # Verify DB persistence
        tenant.refresh_from_db()
        self.assertEqual(tenant.name, "Updated Tenant")
        self.assertEqual(tenant.kyc_status, KYCStatus.VERIFIED)

    def test_suspend_tenant(self):
        """Test tenant suspension via API"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(
            f"/api/v1/tenants/{tenant.id}/suspend/",
            {"reason": "Violation of terms"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.SUSPENDED)

    def test_suspend_deleted_tenant_fails(self):
        """Test that suspending deleted tenant fails (soft-deleted = not found via ActiveTenantManager)"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        tenant.soft_delete()
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/suspend/")

        # ActiveTenantManager excludes soft-deleted, so this should be 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reactivate_tenant(self):
        """Test tenant reactivation via API"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        tenant.suspend()
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/reactivate/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)

    def test_reactivate_active_tenant_fails(self):
        """Test that reactivating active tenant fails"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/reactivate/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_tenant(self):
        """Test tenant deletion via API"""
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.delete(f"/api/v1/tenants/{tenant.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

    def test_list_tenants(self):
        """Test tenant listing via API returns at least the tenants we created."""
        _uid1, _uid2 = uuid.uuid4().hex[:8], uuid.uuid4().hex[:8]
        Tenant.objects.create(name=f"Tenant {_uid1}", slug=f"tenant-{_uid1}")
        Tenant.objects.create(name=f"Tenant {_uid2}", slug=f"tenant-{_uid2}")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/tenants/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Extract tenant list from paginated or unpaginated response
        if "results" in response.data:
            tenants = response.data["results"]
        elif isinstance(response.data, list):
            tenants = response.data
        else:
            self.fail(f"Unexpected response format: {type(response.data)}")
        self.assertGreaterEqual(len(tenants), 2, "Should return at least the 2 tenants we created")
        # Verify our specific tenants are in the response
        returned_slugs = {t["slug"] for t in tenants}
        self.assertIn(f"tenant-{_uid1}", returned_slugs)
        self.assertIn(f"tenant-{_uid2}", returned_slugs)

    def test_unauthenticated_access_returns_401(self):
        """Test that unauthenticated requests return 401"""
        # Do NOT authenticate
        response = self.client.get("/api/v1/tenants/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.post(
            "/api/v1/tenants/",
            {"name": "Hack", "slug": "hack"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
