"""
Unit tests for APIAnalyticsMiddleware.

Tests middleware behavior for API request tracking: request start-time
annotation, non-API path skipping, response latency calculation, tenant/user
extraction, and graceful failure when tracking errors occur.
"""

import time
from unittest.mock import Mock, patch

import pytest
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from hub.apps.api.analytics.middleware import APIAnalyticsMiddleware

pytestmark = pytest.mark.django_db(transaction=True)


class APIAnalyticsMiddlewareTest(TestCase):
    """Test APIAnalyticsMiddleware — request/response processing"""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = Mock(return_value=HttpResponse(status=200))
        self.middleware = APIAnalyticsMiddleware(self.get_response)

    # ── process_request ──────────────────────────────────────────────

    def test_process_request_sets_start_time_for_api_path(self):
        """Middleware records start time for /api/ paths"""
        request = self.factory.get("/api/v1/assets/")
        request._body = b""

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "_api_analytics_start_time"))
        self.assertIsInstance(request._api_analytics_start_time, float)

    def test_process_request_sets_request_size(self):
        """Middleware records request body size"""
        request = self.factory.get("/api/v1/assets/")
        # force body access
        _ = request.body
        request._body = b'{"key":"value"}'

        self.middleware.process_request(request)

        self.assertTrue(hasattr(request, "_api_analytics_request_size"))

    def test_process_request_skips_non_api_path(self):
        """Middleware does NOT annotate non-API requests"""
        request = self.factory.get("/health/")
        request._body = b""

        self.middleware.process_request(request)

        self.assertFalse(hasattr(request, "_api_analytics_start_time"))

    def test_process_request_skips_admin_path(self):
        """Middleware skips Django admin paths"""
        request = self.factory.get("/admin/login/")
        request._body = b""

        self.middleware.process_request(request)

        self.assertFalse(hasattr(request, "_api_analytics_start_time"))

    # ── process_response ─────────────────────────────────────────────

    @patch("hub.apps.api.analytics.middleware.APIAnalyticsService.track_request")
    def test_process_response_calls_track_request(self, mock_track):
        """Middleware calls APIAnalyticsService.track_request for API responses"""
        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request._api_analytics_request_size = 100
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = "user-id-1"
        response = HttpResponse(content=b'{"data":"value"}', status=200)

        self.middleware.process_response(request, response)

        mock_track.assert_called_once()
        call_kwargs = mock_track.call_args[1]
        self.assertEqual(call_kwargs["tenant_id"], "550e8400-e29b-41d4-a716-446655440000")
        self.assertEqual(call_kwargs["endpoint_path"], "/api/v1/assets/")
        self.assertEqual(call_kwargs["method"], "GET")
        self.assertEqual(call_kwargs["status_code"], 200)
        self.assertIsNotNone(call_kwargs["latency_ms"])
        self.assertEqual(call_kwargs["user_id"], "user-id-1")

    def test_process_response_skips_non_api_path(self):
        """Middleware does NOT track non-API responses"""
        request = self.factory.get("/health/")
        response = HttpResponse(status=200)

        result = self.middleware.process_response(request, response)

        self.assertEqual(result, response)

    def test_process_response_skips_when_no_tenant(self):
        """Middleware skips tracking when tenant context is missing"""
        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request.user = Mock()
        request.user.is_authenticated = False
        # No tenant_id or tenant attribute
        response = HttpResponse(status=200)

        result = self.middleware.process_response(request, response)

        self.assertEqual(result, response)

    def test_process_response_uses_tenant_attribute(self):
        """Middleware extracts tenant from request.tenant when tenant_id is absent"""
        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request.user = Mock()
        request.user.is_authenticated = False
        request.tenant = Mock()
        request.tenant.id = "tenant-from-obj"

        with patch(
            "hub.apps.api.analytics.middleware.APIAnalyticsService.track_request"
        ) as mock_track:
            self.middleware.process_response(request, HttpResponse(status=200))

            mock_track.assert_called_once()
            self.assertEqual(mock_track.call_args[1]["tenant_id"], "tenant-from-obj")

    def test_process_response_calculates_latency(self):
        """Middleware calculates latency from stored start time"""
        request = self.factory.get("/api/v1/assets/")
        start = time.time() - 0.150  # 150ms ago
        request._api_analytics_start_time = start
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.user = Mock()
        request.user.is_authenticated = False

        with patch(
            "hub.apps.api.analytics.middleware.APIAnalyticsService.track_request"
        ) as mock_track:
            self.middleware.process_response(request, HttpResponse(status=200))

            latency = mock_track.call_args[1]["latency_ms"]
            self.assertGreaterEqual(latency, 140)  # at least 140ms
            self.assertLessEqual(latency, 200)  # at most 200ms (with some tolerance)

    # ── Error handling ───────────────────────────────────────────────

    @patch("hub.apps.api.analytics.middleware.APIAnalyticsService.track_request")
    def test_process_response_survives_tracking_error(self, mock_track):
        """Middleware does NOT crash when tracking raises an exception"""
        mock_track.side_effect = Exception("DB connection lost")

        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.user = Mock()
        request.user.is_authenticated = False
        response = HttpResponse(status=200)

        # Should not raise
        result = self.middleware.process_response(request, response)
        self.assertEqual(result.status_code, 200)

    # ── Callable behavior ────────────────────────────────────────────

    def test_middleware_is_django_callable(self):
        """Middleware works as standard Django middleware (__call__ pattern)"""
        request = self.factory.get("/health/")

        response = self.middleware(request)

        self.assertIsInstance(response, HttpResponse)
        self.get_response.assert_called_once_with(request)

    def test_middleware_api_path_full_flow(self):
        """Full middleware flow for an API path (request → response)"""
        request = self.factory.get("/api/v1/assets/")
        request.user = Mock()
        request.user.is_authenticated = True
        request.user.id = "user-123"
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"

        with patch("hub.apps.api.analytics.middleware.APIAnalyticsService.track_request"):
            response = self.middleware(request)

            self.assertEqual(response.status_code, 200)

    # ── Status code tracking ─────────────────────────────────────────

    def test_process_response_tracks_error_status_codes(self):
        """Middleware tracks 4xx/5xx status codes correctly"""
        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.user = Mock()
        request.user.is_authenticated = False

        with patch(
            "hub.apps.api.analytics.middleware.APIAnalyticsService.track_request"
        ) as mock_track:
            self.middleware.process_response(request, HttpResponse(status=404))

            self.assertEqual(mock_track.call_args[1]["status_code"], 404)

    def test_process_response_tracks_server_errors(self):
        """Middleware tracks 500 status codes"""
        request = self.factory.get("/api/v1/assets/")
        request._api_analytics_start_time = time.time()
        request.tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        request.user = Mock()
        request.user.is_authenticated = False

        with patch(
            "hub.apps.api.analytics.middleware.APIAnalyticsService.track_request"
        ) as mock_track:
            self.middleware.process_response(request, HttpResponse(status=500))

            self.assertEqual(mock_track.call_args[1]["status_code"], 500)
