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

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TenantViewSetTest(TestCase):
    """Test TenantViewSet with real User model."""

    def setUp(self):
        """Set up test fixtures: platform admin (tenant=None) and regular user (with tenant)."""
        self.client = APIClient()
        self.tenant_for_user = Tenant.objects.create(name="User Tenant", slug="user-tenant")
        self.platform_admin = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant_for_user,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_create_tenant(self):
        """Test tenant creation via API"""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(
            "/api/v1/tenants/",
            {"name": "New Tenant", "slug": "new-tenant", "region": "us-east-1"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], "New Tenant")
        self.assertEqual(response.data["slug"], "new-tenant")
        self.assertEqual(response.data["status"], TenantStatus.ACTIVE)
        self.assertEqual(response.data["kyc_status"], KYCStatus.UNVERIFIED)

    def test_create_tenant_requires_platform_admin(self):
        """Test that only platform admins can create tenants"""
        self.client.force_authenticate(user=self.regular_user)

        response = self.client.post(
            "/api/v1/tenants/",
            {"name": "New Tenant", "slug": "new-tenant"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_retrieve_tenant(self):
        """Test tenant retrieval via API"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(f"/api/v1/tenants/{tenant.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Test Tenant")

    def test_update_tenant(self):
        """Test tenant update via API"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.patch(
            f"/api/v1/tenants/{tenant.id}/",
            {"name": "Updated Tenant", "kyc_status": KYCStatus.VERIFIED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Tenant")
        self.assertEqual(response.data["kyc_status"], KYCStatus.VERIFIED)

    def test_suspend_tenant(self):
        """Test tenant suspension via API"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
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
        """Test that suspending deleted tenant fails"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        tenant.soft_delete()
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/suspend/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reactivate_tenant(self):
        """Test tenant reactivation via API"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        tenant.suspend()
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/reactivate/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.ACTIVE)

    def test_reactivate_active_tenant_fails(self):
        """Test that reactivating active tenant fails"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.post(f"/api/v1/tenants/{tenant.id}/reactivate/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_delete_tenant(self):
        """Test tenant deletion via API"""
        tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.delete(f"/api/v1/tenants/{tenant.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        tenant.refresh_from_db()
        self.assertEqual(tenant.status, TenantStatus.DELETED)
        self.assertIsNotNone(tenant.deleted_at)

    def test_list_tenants(self):
        """Test tenant listing via API"""
        Tenant.objects.create(name="Tenant 1", slug="tenant-1")
        Tenant.objects.create(name="Tenant 2", slug="tenant-2")
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/tenants/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response may be paginated (results) or unpaginated (list)
        self.assertTrue(
            "results" in response.data or isinstance(response.data, list),
            "List response should be paginated (results) or a list",
        )
