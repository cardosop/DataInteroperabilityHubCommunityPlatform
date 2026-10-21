"""
Admin Health API integration tests.

Covers GET /api/v1/admin/health/ — PLATFORM_ADMIN component health
with full database, Redis, and optional ClamAV/BaaS status.
"""

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from tests.fixtures.test_data_factories import TenantFactory, UserFactory


class TestAdminHealthAPI(TestCase):
    """GET /api/v1/admin/health/ — admin health endpoint tests."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant(
            slug=f"admin-health-{uuid.uuid4().hex[:8]}",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create platform admin (endpoint requires PLATFORM_ADMIN)
        self.admin = UserFactory.create_user(
            tenant=self.tenant,
            email=f"admin-health-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            status="ACTIVE",
            is_platform_admin=True,
        )
        # Login as platform admin
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.admin.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.access_token = resp.data["access_token"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")

    def test_health_returns_component_status(self):
        """GET /api/v1/admin/health/ returns 200 with component health."""
        response = self.client.get("/api/v1/admin/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("status", response.data)
        self.assertIn("database", response.data)
        self.assertIn("redis", response.data)
        self.assertIn(response.data["status"], ["healthy", "degraded", "unhealthy"])
        # database is a non-empty string — reports its state
        self.assertIsInstance(response.data["database"], str)
        self.assertGreater(len(response.data["database"]), 0)

    def test_health_requires_platform_admin(self):
        """Non-admin user gets 403 on health endpoint."""
        # Create a regular (non-admin) user
        regular_user = UserFactory.create_user(
            tenant=self.tenant,
            email=f"regular-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            status="ACTIVE",
        )
        regular_client = APIClient()
        resp = regular_client.post(
            "/api/v1/auth/login/",
            {"email": regular_user.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        regular_client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.data['access_token']}")
        response = regular_client.get("/api/v1/admin/health/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_health_requires_authentication(self):
        """Unauthenticated request gets 401 on health endpoint."""
        unauth = APIClient()
        response = unauth.get("/api/v1/admin/health/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
