"""
Unit tests for rate limiting middleware.

Tests rate limit application, headers, 429 responses, and Retry-After.
"""

import uuid
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase
from rest_framework.response import Response

from hub.apps.rate_limiting.middleware import RateLimitMiddleware
from hub.apps.rate_limiting.service import RateLimitResult
from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


class RateLimitMiddlewareTest(TestCase):
    """Tests for rate limiting middleware"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.middleware = RateLimitMiddleware(lambda request: None)
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_skips_health_checks(self, mock_settings, mock_check):
        """Test that middleware skips health check endpoints"""
        mock_settings.RATE_LIMIT_ENABLED = True

        request = self.factory.get("/health/")
        response = self.middleware.process_request(request)

        self.assertIsNone(response)
        mock_check.assert_not_called()

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_skips_admin_endpoints(self, mock_settings, mock_check):
        """Test that middleware skips admin endpoints"""
        mock_settings.RATE_LIMIT_ENABLED = True

        request = self.factory.get("/admin/")
        response = self.middleware.process_request(request)

        self.assertIsNone(response)
        mock_check.assert_not_called()

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_skips_non_api_endpoints(self, mock_settings, mock_check):
        """Test that middleware skips non-API endpoints"""
        mock_settings.RATE_LIMIT_ENABLED = True

        request = self.factory.get("/static/css/style.css")
        response = self.middleware.process_request(request)

        self.assertIsNone(response)
        mock_check.assert_not_called()

    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_skips_when_disabled(self, mock_settings):
        """Test that middleware skips when rate limiting is disabled"""
        with patch.object(mock_settings, "RATE_LIMIT_ENABLED", False):
            request = self.factory.post("/api/v1/dq/runs/")
            request.tenant = self.tenant
            response = self.middleware.process_request(request)

            self.assertIsNone(response)

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_allows_request(self, mock_settings, mock_check):
        """Test that middleware allows request when within limits"""
        mock_settings.RATE_LIMIT_ENABLED = True

        # Mock rate limit check to allow
        results = [
            RateLimitResult(
                allowed=True,
                limit=60,
                remaining=55,
                reset_time=1000,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.SUSTAINED,
            )
        ]
        mock_check.return_value = (True, results)

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        response = self.middleware.process_request(request)

        self.assertIsNone(response)  # Should continue processing
        self.assertEqual(getattr(request, "rate_limit_results", None), results)

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_rejects_when_exceeded(self, mock_time, mock_settings, mock_check):
        """Test that middleware rejects request when rate limit exceeded"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0

        # Mock rate limit check to reject
        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        request.id = "test-request-id"
        response = self.middleware.process_request(request)

        self.assertIsNotNone(response)
        self.assertIsInstance(response, Response)
        self.assertEqual(response.status_code, 429)

        # Check response content — DRF Response.data returns the parsed dict
        data = response.data
        self.assertEqual(data["error"]["code"], "RATE_LIMIT_EXCEEDED")
        self.assertEqual(data["error"]["http_status"], 429)
        self.assertEqual(data["error"]["details"]["limit_type"], "tenant")
        self.assertEqual(data["error"]["details"]["retry_after"], 500)  # 1000 - 500

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_sets_retry_after(self, mock_time, mock_settings, mock_check):
        """Test that middleware sets Retry-After header"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0

        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        self.middleware.process_request(request)

        # Should set retry_after on request
        self.assertEqual(getattr(request, "retry_after", None), 500)

    @patch("hub.apps.rate_limiting.middleware.get_rate_limit_headers")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_adds_headers(self, mock_settings, mock_get_headers):
        """Test that middleware adds rate limit headers to response"""
        mock_settings.RATE_LIMIT_ENABLED = True

        mock_get_headers.return_value = {
            "X-RateLimit-Limit": "60",
            "X-RateLimit-Remaining": "55",
            "X-RateLimit-Reset": "1000",
            "X-RateLimit-Category": "dq_run",
        }

        request = self.factory.post("/api/v1/dq/runs/")
        request.rate_limit_results = [
            RateLimitResult(
                allowed=True,
                limit=60,
                remaining=55,
                reset_time=1000,
                limit_type="tenant",
                category=EndpointCategory.DQ_RUN,
                window=TimeWindow.SUSTAINED,
            )
        ]

        response = Mock()
        response.__setitem__ = Mock()

        self.middleware.process_response(request, response)

        # Should call get_rate_limit_headers
        mock_get_headers.assert_called_once_with(request, request.rate_limit_results)
        # Should set the expected rate-limit headers (production code at
        # service.py:248-258 emits these four; Type is conditional).
        set_headers = [call[0][0] for call in response.__setitem__.call_args_list]
        self.assertIn("X-RateLimit-Limit", set_headers)
        self.assertIn("X-RateLimit-Remaining", set_headers)
        self.assertIn("X-RateLimit-Reset", set_headers)
        self.assertIn("X-RateLimit-Category", set_headers)

    @patch("hub.apps.rate_limiting.middleware.get_rate_limit_headers")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_adds_retry_after_header(self, mock_settings, mock_get_headers):
        """Test that middleware adds Retry-After header when limit exceeded"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_get_headers.return_value = {}

        request = self.factory.post("/api/v1/dq/runs/")
        request.retry_after = 60

        response = Mock()
        response.__setitem__ = Mock()

        self.middleware.process_response(request, response)

        # Should add Retry-After header
        response.__setitem__.assert_called_with("Retry-After", "60")

    @patch("hub.apps.rate_limiting.middleware.get_rate_limit_headers")
    @patch("hub.apps.rate_limiting.middleware.settings")
    def test_middleware_no_headers_for_non_api(self, mock_settings, mock_get_headers):
        """Test that middleware doesn't add headers for non-API endpoints"""
        mock_settings.RATE_LIMIT_ENABLED = True

        request = self.factory.get("/static/css/style.css")
        request.rate_limit_results = []

        response = Mock()
        response.__setitem__ = Mock()

        self.middleware.process_response(request, response)

        # Should not call get_rate_limit_headers
        mock_get_headers.assert_not_called()

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_generates_request_id(self, mock_time, mock_settings, mock_check):
        """Test that middleware generates request ID if not present"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0

        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        # No request.id set

        response = self.middleware.process_request(request)

        # Should generate request ID
        self.assertIsNotNone(getattr(request, "id", None))
        data = response.data
        self.assertIn("request_id", data["error"])

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_uses_existing_request_id(self, mock_time, mock_settings, mock_check):
        """Test that middleware uses existing request ID if present"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0

        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        request.id = "existing-request-id"

        response = self.middleware.process_request(request)

        # Should use existing request ID
        data = response.data
        self.assertEqual(data["error"]["request_id"], "existing-request-id")

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_error_format(self, mock_time, mock_settings, mock_check):
        """Test that error response follows standard format"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0

        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        response = self.middleware.process_request(request)

        data = response.data

        # Should have standard error format
        self.assertIn("error", data)
        self.assertIn("code", data["error"])
        self.assertIn("message", data["error"])
        self.assertIn("http_status", data["error"])
        self.assertIn("request_id", data["error"])
        self.assertIn("timestamp", data["error"])
        self.assertIn("details", data["error"])

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_handles_no_results(self, mock_time, mock_settings, mock_check):
        """Test that middleware handles case when no results returned"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 500.0
        mock_check.return_value = (False, [])  # No results

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        response = self.middleware.process_request(request)

        # Should still return 429
        self.assertIsNotNone(response)
        self.assertEqual(response.status_code, 429)
        data = response.data
        self.assertEqual(data["error"]["code"], "RATE_LIMIT_EXCEEDED")

    @patch("hub.apps.rate_limiting.middleware.check_rate_limit")
    @patch("hub.apps.rate_limiting.middleware.settings")
    @patch("time.time")
    def test_middleware_retry_after_minimum(self, mock_time, mock_settings, mock_check):
        """Test that Retry-After is at least 1 second"""
        mock_settings.RATE_LIMIT_ENABLED = True
        mock_time.return_value = 999.0  # Very close to reset_time

        failed_result = RateLimitResult(
            allowed=False,
            limit=60,
            remaining=0,
            reset_time=1000,
            limit_type="tenant",
            category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        mock_check.return_value = (False, [failed_result])

        request = self.factory.post("/api/v1/dq/runs/")
        request.tenant = self.tenant
        response = self.middleware.process_request(request)

        # Retry-After should be at least 1
        data = response.data
        self.assertGreaterEqual(data["error"]["details"]["retry_after"], 1)
