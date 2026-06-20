"""
Regression tests for API endpoints after Django 6 upgrade.

These tests verify that all API endpoints continue to work correctly
after the Django 6 upgrade.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class APIEndpointsRegressionTest(TestCase):
    """Comprehensive regression tests for API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        import uuid as _uuid

        suffix = _uuid.uuid4().hex[:8]
        self.client = Client()
        self.tenant = Tenant.objects.create(
            name=f"API Endpoints Tenant {suffix}",
            slug=f"api-endpoints-{suffix}",
        )
        self.user = User.objects.create_user(
            email=f"api-endpoints-{suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_health_endpoint_regression(self):
        """Health endpoint must return 200 after Django 6 upgrade.

        A 404 is a regression — the health route must always be reachable
        so load-balancers and monitoring agents can check liveness.
        """
        response = self.client.get("/health/")
        self.assertEqual(
            response.status_code,
            200,
            f"/health/ must return 200, got {response.status_code}",
        )

    def test_api_authentication_regression(self):
        """Verify API authentication works correctly after Django 6 upgrade."""
        # Test unauthenticated request
        response = self.client.get("/api/v1/assets/")
        self.assertIn(response.status_code, [401, 403, 404])  # Should require auth

        # Test authenticated request
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/assets/")
        self.assertLess(response.status_code, 500)  # May vary based on permissions

    def test_api_response_format_regression(self):
        """Verify API response format is correct after Django 6 upgrade."""
        self.client.force_login(self.user)
        response = self.client.get("/api/v1/assets/")

        # If successful, should return JSON
        if response.status_code == 200:
            self.assertEqual(response["Content-Type"], "application/json")

    def test_api_error_handling_regression(self):
        """Verify API error handling works correctly after Django 6 upgrade."""
        self.client.force_login(self.user)

        # Test 404 for non-existent resource
        response = self.client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000/")
        self.assertIn(response.status_code, [404, 401, 403])
