"""
Integration tests for REST API endpoints.

Tests cover all major API endpoints to ensure they work correctly.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()

# Mark all tests in this class to use database with transactions
# This ensures proper handling of Django's TestCase with pytest-django
pytestmark = pytest.mark.django_db(transaction=True)


class APIIntegrationTest(TestCase):
    """Integration tests for REST API"""

    @override_settings(ENVIRONMENT="test")
    def setUp(self):
        """Set up test fixtures.

        ``ENVIRONMENT=test`` is pinned explicitly as defence-in-depth
        against test-module contamination: ``test_mailhog_proxy.py``
        runs ``@override_settings(ENVIRONMENT="production")`` tests
        and, with ``pytest.mark.django_db`` on a non-TestCase class,
        the cleanup order can leave a stale URL-resolver state that
        causes ``/api-docs/*`` to return 404 instead of 200.
        """
        uid = uuid.uuid4().hex[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_api_info_endpoint(self):
        """Test API info endpoint"""
        response = self.client.get("/api/v1/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("name", response.data)
        self.assertIn("version", response.data)
        self.assertIn("endpoints", response.data)

    def test_openapi_schema_endpoint(self):
        """Test OpenAPI schema endpoint"""
        response = self.client.get("/api-docs/openapi.json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("openapi", response.data)
        self.assertIn("info", response.data)
        self.assertIn("paths", response.data)

    def test_swagger_ui_endpoint(self):
        """Test Swagger UI endpoint"""
        response = self.client.get("/api-docs/")

        # Should return HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])

    def test_redoc_endpoint(self):
        """Test ReDoc endpoint"""
        response = self.client.get("/api-docs/redoc/")

        # Should return HTML
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("text/html", response["Content-Type"])

    def test_error_response_format(self):
        """Test that error responses follow standardized format"""
        # Make request to non-existent endpoint
        response = self.client.get("/api/v1/nonexistent/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)
        self.assertIn("code", response.data["error"])
        self.assertIn("message", response.data["error"])
        self.assertIn("http_status", response.data["error"])
        self.assertIn("request_id", response.data["error"])
        self.assertIn("timestamp", response.data["error"])

    def test_request_id_header(self):
        """Test that request ID is included in response headers"""
        response = self.client.get("/api/v1/")

        self.assertIn("X-Request-ID", response)
        self.assertIsNotNone(response["X-Request-ID"])

    def test_rate_limit_headers(self):
        """Test that rate limit headers are included when rate limiting is enabled."""
        from django.conf import settings

        response = self.client.get("/api/v1/")

        if not getattr(settings, "RATE_LIMIT_ENABLED", True):
            self.skipTest("Rate limiting is explicitly disabled via settings.RATE_LIMIT_ENABLED")

        # When rate limiting is enabled, headers must be present
        self.assertIn(
            "X-RateLimit-Limit",
            response.headers,
            "X-RateLimit-Limit header missing (rate limiting is enabled)",
        )
        self.assertIn(
            "X-RateLimit-Remaining",
            response.headers,
            "X-RateLimit-Remaining header missing (rate limiting is enabled)",
        )

    def test_authentication_required(self):
        """Test that authentication is required for protected endpoints"""
        # Create unauthenticated client
        client = APIClient()

        # Try to access protected endpoint
        response = client.get("/api/v1/assets/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error"]["code"], "AUTH_UNAUTHORIZED")
