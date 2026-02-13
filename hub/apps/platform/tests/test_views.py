"""
Minimal unit tests for Platform Admin views (Gap #2, task 1.5).

Tests permission enforcement (IsPlatformAdmin) and that platform endpoints
respond correctly. Uses real User, Tenant, APIClient; no mocks/stubs.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class TestPlatformTenantViewSetPermissions(TestCase):
    """Platform tenant endpoints require IsPlatformAdmin."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Platform Test Tenant",
            slug="platform-test-tenant",
        )
        self.platform_admin = User.objects.create_user(
            email="platform-admin@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email="regular@example.com",
            password="testpass123",
            tenant=self.tenant,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_platform_tenant_list_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/tenants/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_list_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/tenants/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_platform_tenant_retrieve_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/{id}/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(
            f"/api/v1/platform/tenants/{self.tenant.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_retrieve_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/{id}/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(
            f"/api/v1/platform/tenants/{self.tenant.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "platform-test-tenant")

    def test_platform_tenant_usage_requires_platform_admin(self):
        """GET /api/v1/platform/tenants/usage/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/tenants/usage/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_tenant_usage_200_for_platform_admin(self):
        """GET /api/v1/platform/tenants/usage/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/tenants/usage/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)


class TestPlatformUserViewSetPermissions(TestCase):
    """Platform user endpoints require IsPlatformAdmin."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Platform User Test Tenant",
            slug="platform-user-test-tenant",
        )
        self.platform_admin = User.objects.create_user(
            email="platform-admin2@example.com",
            password="testpass123",
            tenant=None,
            is_platform_admin=True,
            status=UserStatus.ACTIVE,
        )
        self.regular_user = User.objects.create_user(
            email="regular2@example.com",
            password="testpass123",
            tenant=self.tenant,
            is_platform_admin=False,
            status=UserStatus.ACTIVE,
        )

    def test_platform_user_list_requires_platform_admin(self):
        """GET /api/v1/platform/users/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get("/api/v1/platform/users/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_user_list_200_for_platform_admin(self):
        """GET /api/v1/platform/users/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get("/api/v1/platform/users/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)

    def test_platform_user_retrieve_requires_platform_admin(self):
        """GET /api/v1/platform/users/{id}/ returns 403 for non-platform-admin."""
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(
            f"/api/v1/platform/users/{self.regular_user.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_user_retrieve_200_for_platform_admin(self):
        """GET /api/v1/platform/users/{id}/ returns 200 for platform admin."""
        self.client.force_authenticate(user=self.platform_admin)
        response = self.client.get(
            f"/api/v1/platform/users/{self.regular_user.id}/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
