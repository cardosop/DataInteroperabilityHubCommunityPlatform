"""
Tests for API versioning headers (Phase 25.6.2).

Tests that all API responses include version headers.
No mocks - uses real API endpoints.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.api.versioning import APIVersionManager, DeprecatedEndpoint
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
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", status="ACTIVE"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_version_headers_present(self):
        """Test that version headers are present and correct for all API responses."""
        endpoints = [
            "/api/v1/assets/",
            "/api/v1/datasets/",
            "/api/v1/tenants/me/usage/",
            "/api/v1/billing/subscription/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)

            # Check version headers are present AND have correct values
            self.assertIn(
                "X-API-Version",
                response.headers,
                f"{endpoint} missing X-API-Version header",
            )
            self.assertIn(
                "X-API-Supported-Versions",
                response.headers,
                f"{endpoint} missing X-API-Supported-Versions header",
            )
            self.assertEqual(
                response.headers["X-API-Version"],
                "v1.0.0",
                f"{endpoint} has wrong X-API-Version",
            )
            self.assertIn(
                "v1.0.0",
                response.headers["X-API-Supported-Versions"],
                f"{endpoint} missing v1.0.0 in supported versions",
            )

    def test_non_deprecated_endpoints_omit_deprecation_headers(self):
        """Active endpoints must NOT carry API-versioning deprecation headers.

        Uses /api/v1/tenants/me/ because /api/v1/assets/ carries
        AssetVisibilityDeprecationHeadersMiddleware Sunset/Deprecation
        headers (Phase 250.3.B) which are unrelated to API versioning.
        """
        response = self.client.get("/api/v1/tenants/me/")
        self.assertNotIn(
            "X-API-Deprecated",
            response.headers,
            "Active endpoint should not have X-API-Deprecated header",
        )
        self.assertNotIn(
            "Sunset",
            response.headers,
            "Active endpoint should not have Sunset header",
        )

    def test_deprecated_endpoints_carry_deprecation_headers(self):
        """Deprecated endpoints MUST carry X-API-Deprecated, Sunset, and Link headers.

        Registers a test deprecated endpoint with a FUTURE sunset date
        (is_sunset() must be False — headers are only added when the
        endpoint is deprecated but NOT yet sunset).
        """
        test_dep = DeprecatedEndpoint(
            path="/api/v1/test-deprecated-hdr/",
            method="GET",
            deprecated_since="2026-01-01",
            sunset_date="2027-06-05",  # Future date so is_sunset() = False
            replacement="/api/v2/test/",
            migration_guide="Test migration guide",
        )
        APIVersionManager.register_deprecated_endpoint(test_dep)

        try:
            response = self.client.get("/api/v1/test-deprecated-hdr/")
            # The endpoint resolves to the api_not_found catch-all (404).
            # The APIVersionMiddleware should still add deprecation headers
            # because the path IS registered in DEPRECATED_ENDPOINTS.
            self.assertIn(
                "X-API-Deprecated",
                response.headers,
                "Deprecated endpoint must carry X-API-Deprecated",
            )
            self.assertEqual(response.headers["X-API-Deprecated"], "true")
            self.assertIn(
                "Sunset", response.headers, "Deprecated endpoint must carry Sunset header"
            )
            self.assertIn("Link", response.headers, "Deprecated endpoint must carry Link header")
        finally:
            # Clean up to avoid polluting subsequent tests.
            key = "GET:/api/v1/test-deprecated-hdr/"
            APIVersionManager.DEPRECATED_ENDPOINTS.pop(key, None)
