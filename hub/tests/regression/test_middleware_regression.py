"""
Regression tests for all middleware after Django 6 upgrade.

These tests verify that all middleware continues to work correctly
with Django 6 patterns and doesn't break existing functionality.
"""

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse, JsonResponse
from django.test import Client, RequestFactory, TestCase

from hub.apps.api.middleware import RequestIDMiddleware
from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.observability.middleware import MetricsMiddleware
from hub.apps.rate_limiting.middleware import RateLimitMiddleware
from hub.apps.tenants.middleware import TenantSuspensionMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MiddlewareRegressionTest(TestCase):
    """Comprehensive regression tests for all middleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = Client()
        import uuid as _uuid

        suffix = _uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Middleware Tenant {suffix}",
            slug=f"middleware-{suffix}",
        )
        self.user = User.objects.create_user(
            email=f"middleware-{suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    def test_request_id_middleware_regression(self):
        """Verify RequestIDMiddleware works correctly after Django 6 upgrade."""
        get_response = lambda request: HttpResponse()
        middleware = RequestIDMiddleware(get_response)

        request = self.factory.get("/api/v1/assets/")
        response = middleware(request)

        # Verify response
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)

        # Verify request ID was generated
        self.assertTrue(hasattr(request, "request_id"))
        self.assertIsNotNone(request.request_id)

        # Verify request ID in response headers
        self.assertIn("X-Request-ID", response)
        self.assertEqual(response["X-Request-ID"], request.request_id)

    def test_tenant_scoping_middleware_regression(self):
        """Verify TenantScopingMiddleware works correctly after Django 6 upgrade."""
        get_response = lambda request: HttpResponse()
        middleware = TenantScopingMiddleware(get_response)

        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        response = middleware(request)

        # Verify response
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)

        # Verify tenant was set
        self.assertTrue(hasattr(request, "tenant_id") or hasattr(request, "tenant"))

    def test_tenant_suspension_middleware_regression(self):
        """Verify TenantSuspensionMiddleware works correctly after Django 6 upgrade."""
        get_response = lambda request: HttpResponse()
        middleware = TenantSuspensionMiddleware(get_response)

        # Test with active tenant
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user
        request.tenant = self.tenant

        response = middleware(request)

        # Verify response
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)

    def test_rate_limit_middleware_regression(self):
        """Verify RateLimitMiddleware works correctly after Django 6 upgrade."""
        get_response = lambda request: HttpResponse()
        middleware = RateLimitMiddleware(get_response)

        request = self.factory.get("/api/v1/assets/")
        request.tenant = self.tenant

        response = middleware(request)

        # Verify response (should allow request or return 429)
        self.assertIsInstance(response, (HttpResponse, JsonResponse))
        if isinstance(response, JsonResponse):
            # Rate limited
            self.assertEqual(response.status_code, 429)
        else:
            # Allowed
            self.assertEqual(response.status_code, 200)

    def test_metrics_middleware_regression(self):
        """Verify MetricsMiddleware works correctly after Django 6 upgrade."""
        get_response = lambda request: HttpResponse()
        middleware = MetricsMiddleware(get_response)

        request = self.factory.get("/api/v1/assets/")
        response = middleware(request)

        # Verify response
        self.assertIsInstance(response, HttpResponse)
        self.assertEqual(response.status_code, 200)

    def test_middleware_chain_regression(self):
        """Verify middleware chain works correctly after Django 6 upgrade."""
        # Test that all middleware work together
        client = Client()

        # Authenticate
        client.force_login(self.user)

        # Make request
        response = client.get("/api/v1/assets/")

        # Verify response
        self.assertLess(response.status_code, 500)  # May vary based on auth

        # Verify request ID header is present
        if "X-Request-ID" in response:
            self.assertIsNotNone(response["X-Request-ID"])

    def test_middleware_performance_regression(self):
        """Verify middleware performance hasn't degraded after Django 6 upgrade."""
        import time

        get_response = lambda request: HttpResponse()
        middleware = RequestIDMiddleware(get_response)

        request = self.factory.get("/api/v1/assets/")

        # Time middleware execution
        start = time.time()
        for _ in range(100):
            middleware(request)
        elapsed = time.time() - start

        # Should be fast (< 0.1s for 100 requests)
        self.assertLess(elapsed, 0.1, f"Middleware too slow: {elapsed:.3f}s for 100 requests")
