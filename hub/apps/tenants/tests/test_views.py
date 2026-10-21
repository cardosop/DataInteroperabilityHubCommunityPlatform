"""
Unit tests for Tenant API views.

Uses real User model (no mocks/stubs). Platform admin has tenant=None; regular user has a tenant.
"""

import uuid

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
        """Test that suspending deleted tenant fails with 400 (meaningful error).

        The view deliberately uses ``all_objects`` to find soft-deleted tenants
        and returns a meaningful 400 ``Cannot suspend a deleted tenant`` rather
        than a misleading 404.
        """
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        tenant.soft_delete()
        self.client.force_authenticate(user=self.platform_admin)

        _response = self.client.post(f"/api/v1/tenants/{tenant.id}/suspend/")
