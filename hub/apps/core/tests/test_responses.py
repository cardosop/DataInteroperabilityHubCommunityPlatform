"""
Tests for ``hub.apps.core.responses``.

Covers api_error_response, error_response, and handle_service_exception
end-to-end — verifying the standardized error response contract.
"""

from django.test import SimpleTestCase
from rest_framework import status

from hub.apps.core.responses import (
    api_error_response,
    error_response,
    handle_service_exception,
)
from hub.apps.core.services.base import (
    ConflictError,
    NotFoundError,
    PermissionError,
)
from hub.apps.core.services.base import (
    ValidationError as ServiceValidationError,
)


class ApiErrorResponseTests(SimpleTestCase):
    """Tests for api_error_response() — the primary error response builder."""

    def test_returns_response_with_standard_schema(self):
        """Response has detail, code, details keys."""
        resp = api_error_response("bad input", status.HTTP_400_BAD_REQUEST)
        assert resp.status_code == 400
        data = resp.data
        assert data["detail"] == "bad input"
        assert "code" in data
        assert "details" in data

    def test_infers_code_from_status_400(self):
        """HTTP 400 → VALIDATION_ERROR."""
        resp = api_error_response("nope", status.HTTP_400_BAD_REQUEST)
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_infers_code_from_status_401(self):
        """HTTP 401 → AUTH_UNAUTHORIZED."""
        resp = api_error_response("auth required", status.HTTP_401_UNAUTHORIZED)
        assert resp.data["code"] == "AUTH_UNAUTHORIZED"

    def test_infers_code_from_status_403(self):
        """HTTP 403 → PERMISSION_DENIED."""
        resp = api_error_response("forbidden", status.HTTP_403_FORBIDDEN)
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_infers_code_from_status_404(self):
        """HTTP 404 → NOT_FOUND."""
        resp = api_error_response("missing", status.HTTP_404_NOT_FOUND)
        assert resp.data["code"] == "NOT_FOUND"

    def test_infers_code_from_status_409(self):
        """HTTP 409 → CONFLICT_ERROR."""
        resp = api_error_response("conflict", status.HTTP_409_CONFLICT)
        assert resp.data["code"] == "CONFLICT_ERROR"

    def test_infers_code_from_status_429(self):
        """HTTP 429 → RATE_LIMIT_EXCEEDED."""
        resp = api_error_response("too fast", status.HTTP_429_TOO_MANY_REQUESTS)
        assert resp.data["code"] == "RATE_LIMIT_EXCEEDED"

    def test_infers_code_from_status_500(self):
        """HTTP 500 → INTERNAL_ERROR."""
        resp = api_error_response("boom", status.HTTP_500_INTERNAL_SERVER_ERROR)
        assert resp.data["code"] == "INTERNAL_ERROR"

    def test_infers_code_from_status_502(self):
        """HTTP 502 → SERVICE_UNAVAILABLE."""
        resp = api_error_response("bad gw", status.HTTP_502_BAD_GATEWAY)
        assert resp.data["code"] == "SERVICE_UNAVAILABLE"

    def test_infers_code_from_status_503(self):
        """HTTP 503 → SERVICE_UNAVAILABLE."""
        resp = api_error_response("down", status.HTTP_503_SERVICE_UNAVAILABLE)
        assert resp.data["code"] == "SERVICE_UNAVAILABLE"

    def test_unknown_status_defaults_to_unknown_error(self):
        """Unmapped HTTP status → UNKNOWN_ERROR."""
        resp = api_error_response("teapot", 418)
        assert resp.status_code == 418
        assert resp.data["code"] == "UNKNOWN_ERROR"

    def test_explicit_code_overrides_inferred(self):
        """Explicit code parameter wins over inferred code."""
        resp = api_error_response("msg", status.HTTP_400_BAD_REQUEST, code="CUSTOM_CODE")
        assert resp.data["code"] == "CUSTOM_CODE"

    def test_details_defaults_to_empty_dict(self):
        """When details is not provided, defaults to {}."""
        resp = api_error_response("msg", status.HTTP_400_BAD_REQUEST)
        assert resp.data["details"] == {}

    def test_details_passed_through(self):
        """Details dict is passed through to response."""
        resp = api_error_response("msg", status.HTTP_400_BAD_REQUEST, details={"field": "name"})
        assert resp.data["details"] == {"field": "name"}

    def test_null_details_treated_as_empty(self):
        """Passing details=None defaults to empty dict."""
        resp = api_error_response("msg", status.HTTP_400_BAD_REQUEST, details=None)
        assert resp.data["details"] == {}


class ErrorResponseLegacyTests(SimpleTestCase):
    """Tests for error_response() — legacy format."""

    def test_legacy_format_has_error_key(self):
        """Legacy format uses 'error' key, not 'detail'."""
        resp = error_response("bad", "VALIDATION_ERROR")
        assert resp.data["error"] == "bad"
        assert resp.data["code"] == "VALIDATION_ERROR"

    def test_infers_http_status_from_code(self):
        """VALIDATION_ERROR → 400, NOT_FOUND → 404, etc."""
        resp = error_response("x", "VALIDATION_ERROR")
        assert resp.status_code == 400

        resp = error_response("x", "NOT_FOUND")
        assert resp.status_code == 404

        resp = error_response("x", "CONFLICT_ERROR")
        assert resp.status_code == 409

        resp = error_response("x", "PERMISSION_DENIED")
        assert resp.status_code == 403

    def test_unknown_code_defaults_to_400(self):
        """Unmapped code → 400."""
        resp = error_response("x", "WEIRD_CODE")
        assert resp.status_code == 400

    def test_explicit_http_status_overrides_inferred(self):
        """Explicit http_status parameter wins over code-based inference."""
        resp = error_response("x", "VALIDATION_ERROR", http_status=422)
        assert resp.status_code == 422

    def test_details_defaults_to_empty_dict(self):
        """No details → {}."""
        resp = error_response("x", "VALIDATION_ERROR")
        assert resp.data["details"] == {}


class HandleServiceExceptionTests(SimpleTestCase):
    """Tests for handle_service_exception() mapping."""

    def test_validation_error_maps_to_400(self):
        exc = ServiceValidationError(message="invalid field")
        resp = handle_service_exception(exc)
        assert resp.status_code == 400
        assert resp.data["code"] == "VALIDATION_ERROR"
        assert resp.data["detail"] == "invalid field"

    def test_not_found_error_maps_to_404(self):
        exc = NotFoundError(message="not here")
        resp = handle_service_exception(exc)
        assert resp.status_code == 404
        assert resp.data["code"] == "NOT_FOUND"

    def test_conflict_error_maps_to_409(self):
        exc = ConflictError(message="already exists")
        resp = handle_service_exception(exc)
        assert resp.status_code == 409
        assert resp.data["code"] == "CONFLICT_ERROR"

    def test_permission_error_maps_to_403(self):
        exc = PermissionError(message="denied")
        resp = handle_service_exception(exc)
        assert resp.status_code == 403
        assert resp.data["code"] == "PERMISSION_DENIED"

    def test_unknown_exception_maps_to_500(self):
        exc = ValueError("unexpected")
        resp = handle_service_exception(exc)
        assert resp.status_code == 500
        assert resp.data["code"] == "INTERNAL_ERROR"
        assert "unexpected" in resp.data["detail"]

    def test_service_exception_preserves_custom_http_status(self):
        exc = ServiceValidationError(message="nope")
        exc.http_status = 422
        resp = handle_service_exception(exc)
        assert resp.status_code == 422

    def test_service_exception_preserves_custom_code(self):
        exc = NotFoundError(message="nope")
        exc.code = "CUSTOM_NOT_FOUND"
        resp = handle_service_exception(exc)
        assert resp.data["code"] == "CUSTOM_NOT_FOUND"

    def test_service_exception_preserves_details(self):
        exc = ServiceValidationError(message="nope", details={"field": "email", "reason": "format"})
        resp = handle_service_exception(exc)
        assert resp.data["details"] == {"field": "email", "reason": "format"}
