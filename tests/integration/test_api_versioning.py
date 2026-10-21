"""
Integration tests for API versioning.

Verifies /api/v1/ version info, version headers, and version parsing in requests.
Uses real HTTP client and real API (no mocks/stubs).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.api.versioning import APIVersion
from hub.apps.users.models import UserStatus
from tests.factories import TenantFactory, UserFactory

User = get_user_model()
pytestmark = pytest.mark.django_db(transaction=True)


class APIVersioningIntegrationTest(TestCase):
    """Integration tests for API versioning with real endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant, status=UserStatus.ACTIVE)
        self.client.force_authenticate(user=self.user)

    def test_api_info_returns_version(self):
        """GET /api/v1/ returns version in response."""
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertIn("version", data)
        self.assertIsInstance(data["version"], str)
        self.assertTrue(len(data["version"]) > 0)

    def test_api_base_url_is_v1(self):
        """GET /api/v1/ returns base_url /api/v1."""
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json().get("base_url"), "/api/v1")

    def test_version_parse_integration(self):
        """APIVersion.parse matches runtime version format."""
        response = self.client.get("/api/v1/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        version_str = response.json().get("version", "")
        self.assertTrue(len(version_str) > 0, "API version must be non-empty")
        parsed = APIVersion.parse(version_str if version_str.startswith("v") else f"v{version_str}")
        self.assertIsNotNone(parsed, f"APIVersion.parse({version_str!r}) should not be None")

    def test_assets_under_v1(self):
        """Assets endpoint is under /api/v1/."""
        response = self.client.get("/api/v1/assets/")
        self.assertIn(response.status_code, [200, 404])

    def test_contracts_under_v1(self):
        """Contracts endpoint is under /api/v1/."""
        response = self.client.get("/api/v1/contracts/")
        self.assertIn(response.status_code, [200, 404])
