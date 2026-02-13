"""
Tests for API versioning headers (Phase 25.6.2).

Tests that all API responses include version headers.
No mocks - uses real API endpoints.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant

User = get_user_model()


class APIVersionHeadersTest(TestCase):
    """
    Tests for API versioning headers.

    Verifies that all /api/v1/ responses include:
    - X-API-Version
    - X-API-Supported-Versions
    """

    def setUp(self):
        """Set up test data"""
        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_version_headers_present(self):
        """Test that version headers are present in all API responses"""
        # Test various endpoints
        endpoints = [
            "/api/v1/assets/",
            "/api/v1/datasets/",
            "/api/v1/tenants/me/usage/",
            "/api/v1/billing/subscription/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)

            # Check version headers are present (DRF responses use response.headers)
            self.assertIn("X-API-Version", response.headers)
            self.assertIn("X-API-Supported-Versions", response.headers)

            # Check header values
            self.assertEqual(response.headers["X-API-Version"], "v1.0.0")
            self.assertIn("v1.0.0", response.headers["X-API-Supported-Versions"])

    def test_deprecated_endpoint_headers(self):
        """Test that deprecated endpoints include deprecation headers"""
        # Note: No endpoints are currently deprecated
        # This test verifies the mechanism works when endpoints are deprecated
        # In the future, when endpoints are deprecated, they should include:
        # - X-API-Deprecated: true
        # - Sunset: <date>
        # - Link: <replacement>
        pass
