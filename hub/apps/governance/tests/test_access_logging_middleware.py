"""
Phase 82.1 — Access Logging Middleware tests.

Tests that AccessLoggingMiddleware correctly logs API requests for audit,
extracts resources from paths, maps methods to actions, and maps status
codes to results.
"""
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.http import HttpRequest, HttpResponse
from django.test import TestCase

from hub.apps.governance.middleware import AccessLoggingMiddleware


class AccessLoggingMiddlewareUnitTest(TestCase):
    """Unit tests for AccessLoggingMiddleware — no DB required."""

    def setUp(self):
        self.middleware = AccessLoggingMiddleware(get_response=lambda r: r)

    def _make_request(self, path, method="GET", tenant_id=None,
                      user=None, xff=None, remote_addr="10.0.0.1"):
        request = HttpRequest()
        request.method = method
        request.path = path
        request.META = {
            "REMOTE_ADDR": remote_addr,
            "HTTP_USER_AGENT": "test-agent",
        }
        if xff:
            request.META["HTTP_X_FORWARDED_FOR"] = xff
        if tenant_id:
            request.tenant_id = tenant_id
        else:
            request.tenant_id = None
        if user:
            request.user = user
        else:
            request.user = MagicMock(is_authenticated=False)
        return request

    # ── Resource extraction ──────────────────────────────────────

    def test_extract_resource_from_contract_path(self):
        """Extracts resource type and UUID from /api/v1/contracts/<uuid>/."""
        uid = str(uuid.uuid4())
        rt, rid = self.middleware._extract_resource_from_path(
            f"/api/v1/contracts/{uid}/",
        )
        assert rt == "CONTRACT"
        assert rid == uid

    def test_extract_resource_from_assets_path(self):
        """Extracts ASSET from /api/v1/assets/<uuid>/."""
        uid = str(uuid.uuid4())
        rt, rid = self.middleware._extract_resource_from_path(
            f"/api/v1/assets/{uid}/",
        )
        assert rt == "ASSET"
        assert rid == uid

    def test_extract_resource_nested_path(self):
        """Nested path /api/v1/datasets/<uuid>/versions/ extracts DATASET."""
        uid = str(uuid.uuid4())
        rt, rid = self.middleware._extract_resource_from_path(
            f"/api/v1/datasets/{uid}/versions/",
        )
        assert rt == "DATASET"
        assert rid == uid

    def test_extract_resource_no_uuid_returns_none(self):
        """List path without UUID returns (None, None) — requires both type+id."""
        rt, rid = self.middleware._extract_resource_from_path(
            "/api/v1/contracts/",
        )
        assert rt is None
        assert rid is None

    # ── Method → Action mapping ──────────────────────────────────

    def test_get_maps_to_read(self):
        assert self.middleware._get_action_from_method("GET") == "READ"

    def test_post_maps_to_write(self):
        assert self.middleware._get_action_from_method("POST") == "WRITE"

    def test_put_maps_to_write(self):
        assert self.middleware._get_action_from_method("PUT") == "WRITE"

    def test_patch_maps_to_write(self):
        assert self.middleware._get_action_from_method("PATCH") == "WRITE"

    def test_delete_maps_to_delete(self):
        assert self.middleware._get_action_from_method("DELETE") == "DELETE"

    def test_unknown_method_defaults_to_read(self):
        assert self.middleware._get_action_from_method("OPTIONS") == "READ"

    # ── Status → Result mapping ──────────────────────────────────

    def test_2xx_maps_to_allowed(self):
        assert self.middleware._get_result_from_status(200) == "ALLOWED"
        assert self.middleware._get_result_from_status(201) == "ALLOWED"
        assert self.middleware._get_result_from_status(204) == "ALLOWED"

    def test_403_maps_to_denied(self):
        assert self.middleware._get_result_from_status(403) == "DENIED"

    def test_401_maps_to_denied(self):
        assert self.middleware._get_result_from_status(401) == "DENIED"

    def test_non_forbidden_status_maps_to_allowed(self):
        """Non-401/403 responses are logged as ALLOWED (request was processed, not blocked by access control)."""
        assert self.middleware._get_result_from_status(404) == "ALLOWED"
        assert self.middleware._get_result_from_status(500) == "ALLOWED"
        assert self.middleware._get_result_from_status(400) == "ALLOWED"
        assert self.middleware._get_result_from_status(422) == "ALLOWED"

    # ── Client IP extraction ─────────────────────────────────────

    def test_client_ip_from_x_forwarded_for_first_hop(self):
        request = self._make_request(
            "/api/v1/x/", xff="1.2.3.4, 5.6.7.8",
        )
        assert self.middleware._get_client_ip(request) == "1.2.3.4"

    def test_client_ip_fallback_to_remote_addr(self):
        request = self._make_request(
            "/api/v1/x/", remote_addr="9.8.7.6",
        )
        assert self.middleware._get_client_ip(request) == "9.8.7.6"

    # ── process_response integration ─────────────────────────────

    @patch(
        "hub.apps.governance.middleware.AccessAnalyticsService.log_access",
    )
    def test_api_request_logged(self, mock_log):
        """API request with tenant+resource is logged."""
        uid = str(uuid.uuid4())
        tid = str(uuid.uuid4())
        request = self._make_request(
            f"/api/v1/contracts/{uid}/", tenant_id=tid,
        )
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)
        mock_log.assert_called_once()
        call_kw = mock_log.call_args[1]
        assert call_kw["tenant_id"] == tid
        assert call_kw["resource_type"] == "CONTRACT"
        assert call_kw["resource_id"] == uid
        assert call_kw["action"] == "READ"
        assert call_kw["result"] == "ALLOWED"

    @patch(
        "hub.apps.governance.middleware.AccessAnalyticsService.log_access",
    )
    def test_non_api_path_skipped(self, mock_log):
        """Non-API paths are not logged."""
        request = self._make_request(
            "/health/", tenant_id=str(uuid.uuid4()),
        )
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)
        mock_log.assert_not_called()

    @patch(
        "hub.apps.governance.middleware.AccessAnalyticsService.log_access",
    )
    def test_analytics_endpoint_skipped(self, mock_log):
        """Access analytics endpoints skipped to avoid recursion."""
        uid = str(uuid.uuid4())
        request = self._make_request(
            f"/api/v1/access/analytics/{uid}/",
            tenant_id=str(uuid.uuid4()),
        )
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)
        mock_log.assert_not_called()

    @patch(
        "hub.apps.governance.middleware.AccessAnalyticsService.log_access",
    )
    def test_no_tenant_skipped(self, mock_log):
        """Request without tenant_id is not logged."""
        uid = str(uuid.uuid4())
        request = self._make_request(f"/api/v1/contracts/{uid}/")
        response = HttpResponse(status=200)
        self.middleware.process_response(request, response)
        mock_log.assert_not_called()

    @patch(
        "hub.apps.governance.middleware.AccessAnalyticsService.log_access",
        side_effect=RuntimeError("analytics down"),
    )
    def test_logging_exception_does_not_propagate(self, _mock_log):
        """Exception in log_access is swallowed — response still returned."""
        uid = str(uuid.uuid4())
        request = self._make_request(
            f"/api/v1/contracts/{uid}/",
            tenant_id=str(uuid.uuid4()),
        )
        response = HttpResponse(status=200)
        result = self.middleware.process_response(request, response)
        assert result.status_code == 200
