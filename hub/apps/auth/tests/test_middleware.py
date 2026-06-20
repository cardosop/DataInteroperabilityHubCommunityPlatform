"""
Unit tests for tenant scoping middleware.

All tests use real implementations (no mocks of hub services).
Middleware get_response mock is acceptable for middleware testing per TEST_STRATEGY.md.
"""

import uuid
from unittest.mock import Mock

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from hub.apps.auth.middleware import TenantScopingMiddleware
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User

pytestmark = pytest.mark.django_db(transaction=True)


class TenantScopingMiddlewareTest(TestCase):
    """
    Test TenantScopingMiddleware.

    MIDDLEWARE TESTING: Mocking get_response is acceptable for middleware testing
    as it's a callable passed to middleware, not an internal service.
    """

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        # MIDDLEWARE TESTING: Mocking get_response is acceptable for middleware testing
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = TenantScopingMiddleware(self.get_response)
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_middleware_is_callable_returns_http_response(self):
        """Test that middleware is callable and returns an HttpResponse."""
        request = self.factory.get("/api/v1/assets/")
        response = self.middleware(request)

        self.assertIsNotNone(response, "Middleware __call__ must return a response")
        self.assertIsInstance(response, HttpResponse, "Middleware must return an HttpResponse")

    def test_middleware_calls_get_response(self):
        """Test that middleware calls get_response."""
        request = self.factory.get("/api/v1/assets/")
        self.middleware(request)

        self.get_response.assert_called_once()

    def test_extracts_tenant_from_api_key(self):
        """Test that middleware extracts tenant_id from API key."""
        from hub.apps.auth.models import APIKey

        # Create API key with known plaintext
        APIKey.objects.create(
            tenant=self.tenant,
            name="Test API Key",
            key_hash=APIKey.hash_key("test-key-123"),
            user=self.user,
        )

        request = self.factory.get(
            "/api/v1/assets/",
            HTTP_AUTHORIZATION="ApiKey test-key-123",
        )

        self.middleware.process_request(request)

        # API key lookup must set tenant_id unconditionally
        self.assertTrue(hasattr(request, "tenant_id"))
        self.assertEqual(str(request.tenant_id), str(self.tenant.id))

    def test_extracts_tenant_from_jwt_sets_tenant_id(self):
        """Test that middleware extracts tenant_id from JWT token."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        # Generate JWT token
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        request = self.factory.get("/api/v1/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant.id))

    def test_extracts_tenant_from_jwt_sets_tenant(self):
        """Test that middleware extracts tenant from JWT token."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        # Generate JWT token
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        request = self.factory.get("/api/v1/assets/", HTTP_AUTHORIZATION=f"Bearer {token}")

        self.middleware.process_request(request)

        self.assertIsNotNone(request.tenant)

    def test_extracts_tenant_from_user_sets_tenant_id(self):
        """Test that middleware extracts tenant_id from authenticated user."""
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant.id))

    def test_extracts_tenant_from_user_sets_tenant(self):
        """Test that middleware extracts tenant from authenticated user."""
        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        self.middleware.process_request(request)

        self.assertIsNotNone(request.tenant)

    def test_handles_missing_tenant_gracefully(self):
        """Test that middleware handles unauthenticated request without crashing."""
        request = self.factory.get("/api/v1/assets/")
        # No user, no auth header — middleware must not raise

        result = self.middleware.process_request(request)

        # Middleware should either set tenant_id to None or leave it unset,
        # but never crash. Verify it didn't return an error response.
        if result is not None:
            # If middleware returned a response, it should not be a 500
            self.assertNotEqual(result.status_code, 500)
        # Verify the request object is still usable (not corrupted)
        self.assertTrue(hasattr(request, "META"))

    def test_preserves_existing_tenant_id(self):
        """Test that middleware preserves existing tenant_id."""
        request = self.factory.get("/api/v1/assets/")
        request.tenant_id = str(self.tenant.id)

        self.middleware.process_request(request)

        self.assertEqual(str(request.tenant_id), str(self.tenant.id))

    def test_preserves_existing_tenant(self):
        """Test that middleware preserves existing tenant."""
        request = self.factory.get("/api/v1/assets/")
        request.tenant_id = str(self.tenant.id)

        self.middleware.process_request(request)

        self.assertIsNotNone(request.tenant)

    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        import time

        request = self.factory.get("/api/v1/assets/")
        request.user = self.user

        start = time.time()
        for _ in range(100):
            self.middleware.process_request(request)
        elapsed = time.time() - start

        # Should process 100 requests in less than 1 second
        self.assertLess(elapsed, 1.0, f"Middleware too slow: {elapsed:.3f}s for 100 requests")
