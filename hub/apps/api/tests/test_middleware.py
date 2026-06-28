"""
Unit tests for API middleware (RequestIDMiddleware).
"""

import uuid
from unittest.mock import Mock, patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from hub.apps.api.middleware import RequestIDMiddleware

class RequestIDMiddlewareTest(TestCase):
    """Test RequestIDMiddleware"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse())
        self.middleware = RequestIDMiddleware(self.get_response)

    def test_middleware_is_callable(self):
        """Test that middleware is callable (Django 6 pattern)"""
        request = self.factory.get("/api/v1/assets/")
        response = self.middleware(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once()

    def test_generates_request_id(self):
        """Test that middleware generates request ID if not present"""
        request = self.factory.get("/api/v1/assets/")

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "id"))
        self.assertTrue(hasattr(request, "request_id"))
        self.assertEqual(request.id, request.request_id)
        # Should be a valid UUID string
        try:
            uuid.UUID(request.id)
        except ValueError:
            self.fail("Request ID is not a valid UUID")

    def test_uses_existing_request_id(self):
        """Test that middleware uses existing X-Request-ID header"""
        existing_id = str(uuid.uuid4())
        request = self.factory.get("/api/v1/assets/", HTTP_X_REQUEST_ID=existing_id)

        self.middleware.process_request(request)

        self.assertEqual(request.id, existing_id)
        self.assertEqual(request.request_id, existing_id)

    def test_adds_request_id_to_response(self):
        """Test that middleware adds request ID to response headers"""
        request = self.factory.get("/api/v1/assets/")
        request.request_id = "test-request-id-123"

        response = HttpResponse()
        response = self.middleware.process_response(request, response)

        self.assertEqual(response["X-Request-ID"], "test-request-id-123")

    def test_uses_existing_correlation_id_when_request_id_absent(self):
        """X-Correlation-ID is honored when X-Request-ID isn't sent.

        Frontend convention sends X-Correlation-ID; the middleware should
        adopt it so a single round-trip pair exists. Verified via the
        public contract (response headers) rather than the dynamically-
        attached `request.request_id` attribute.
        """
        existing_id = "e2e-1234567890abcdef"
        request = self.factory.get("/api/v1/assets/", HTTP_X_CORRELATION_ID=existing_id)

        response = self.middleware(request)

        self.assertEqual(response["X-Correlation-ID"], existing_id)
        self.assertEqual(response["X-Request-ID"], existing_id)

    def test_request_id_wins_over_correlation_id_when_both_present(self):
        """Precedence rule: X-Request-ID is the canonical header.

        If both names appear on the same request, X-Request-ID is used so
        existing callers' contracts (server logs, structlog request_id,
        echoed header) don't change behavior in mixed-client environments.
        Verified end-to-end through the middleware's public response.
        """
        request_id = str(uuid.uuid4())
        correlation_id = "e2e-secondary"
        request = self.factory.get(
            "/api/v1/assets/",
            HTTP_X_REQUEST_ID=request_id,
            HTTP_X_CORRELATION_ID=correlation_id,
        )

        response = self.middleware(request)

        self.assertEqual(response["X-Request-ID"], request_id)
        self.assertEqual(response["X-Correlation-ID"], request_id)
        self.assertNotEqual(response["X-Request-ID"], correlation_id)

    def test_response_echoes_both_header_names(self):
        """Both X-Request-ID and X-Correlation-ID are echoed.

        Driven through the full middleware call to exercise the same
        request → response pipeline production traffic uses; avoids the
        legacy `request.request_id = ...` direct-attribute setup which
        bypasses process_request's normalization.
        """
        existing_id = "test-id-9876"
        request = self.factory.get("/api/v1/assets/", HTTP_X_REQUEST_ID=existing_id)

        response = self.middleware(request)

        self.assertEqual(response["X-Request-ID"], existing_id)
        self.assertEqual(response["X-Correlation-ID"], existing_id)

    def test_binds_request_id_to_structlog(self):
        """Test that middleware binds request ID to structlog context"""
        request = self.factory.get("/api/v1/assets/")

        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            self.middleware.process_request(request)

            # Should bind request_id, route, and method
            mock_bind.assert_called_once()
            call_kwargs = mock_bind.call_args[1] if mock_bind.call_args[1] else {}
            self.assertIn("request_id", call_kwargs,
                "request_id was not bound to structlog context")
            self.assertEqual(call_kwargs["route"], "/api/v1/assets/")
            self.assertEqual(call_kwargs["method"], "GET")
            # Request ID should be generated
            self.assertTrue(hasattr(request, "request_id"))

    @pytest.mark.django_db(transaction=True)
    def test_binds_tenant_id_to_structlog(self):
        """Test that middleware binds tenant_id to structlog in response"""
        from hub.apps.tenants.models import Tenant

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        request = self.factory.get("/api/v1/assets/")
        request.tenant = tenant

        response = HttpResponse()

        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            self.middleware.process_response(request, response)

            # Should bind tenant_id
            mock_bind.assert_called_once()
            # Check if tenant_id was bound
            calls = [call[1] for call in mock_bind.call_args_list if "tenant_id" in call[1]]
            self.assertTrue(calls, "tenant_id was never bound to structlog context in any call")
            self.assertEqual(calls[0]["tenant_id"], str(tenant.id))

    @pytest.mark.django_db(transaction=True)
    def test_binds_user_id_to_structlog(self):
        """Test that middleware binds user_id to structlog in response"""
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=tenant
        )

        request = self.factory.get("/api/v1/assets/")
        request.user = user

        response = HttpResponse()

        with patch("structlog.contextvars.bind_contextvars") as mock_bind:
            self.middleware.process_response(request, response)

            # Should bind user_id
            mock_bind.assert_called_once()
            # Check if user_id was bound
            calls = [call[1] for call in mock_bind.call_args_list if "user_id" in call[1]]
            self.assertTrue(calls, "user_id was never bound to structlog context in any call")
            self.assertEqual(calls[0]["user_id"], str(user.id))

    def test_middleware_performance(self):
        """Test middleware performance (should be fast)"""
        import time

        request = self.factory.get("/api/v1/assets/")

        start = time.time()
        for _ in range(1000):
            self.middleware.process_request(request)
        elapsed = time.time() - start

        # Should process 1000 requests in under 2.0 seconds
        # (generous budget to avoid CI flakiness under CPU contention)
        self.assertLess(elapsed, 2.0, f"Middleware too slow: {elapsed:.3f}s for 1000 requests")
