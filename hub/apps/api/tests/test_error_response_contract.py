"""
Phase 277.4.7 — Error response contract tests.

Verifies Phase 274 error codes match StandardResponseFormatter shape:
{error: {code, message, http_status, request_id, details}}.
"""

from __future__ import annotations

import pytest
from django.test import TestCase

from hub.apps.api.standards.response_formats import format_error_response

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.journey("JOURNEY-ERROR-BOUNDARY")
class TestErrorResponseContract(TestCase):
    """Phase 277.4.7 — canonical error envelope shape."""

    def _assert_envelope(self, code, message, http_status, details=None):
        resp = format_error_response(
            error_code=code,
            message=message,
            http_status=http_status,
            details=details,
        )
        data = resp.data
        # W12.5 — the ONE envelope is the canonical FLAT wire shape
        # {"detail", "code", "details"}; the nested {"error": {...}} shape
        # was the second, divergent envelope. (P3-2b finding: the
        # exception HANDLER still emits the nested shape — its tests
        # below pin the handler's current output; the consolidation
        # follow-up moves the handler onto api_error_response.)
        assert "detail" in data, f"Missing 'detail' key in {data}"
        assert "code" in data, f"Missing 'code' key in {data}"
        assert data["code"] == code
        assert data["detail"] == message
        assert resp.status_code == http_status
        if details:
            assert data.get("details") == details

    def test_compliance_threshold_exceeded_shape(self):
        self._assert_envelope(
            "COMPLIANCE_THRESHOLD_EXCEEDED",
            "Risk level HIGH exceeds tenant threshold MEDIUM.",
            422,
            {"risk_level": "HIGH", "threshold": "MEDIUM"},
        )

    def test_semantic_feature_disabled_shape(self):
        self._assert_envelope(
            "SEMANTIC_FEATURE_DISABLED",
            "Semantic feature 'sparql' is disabled for this tenant.",
            403,
            {"action": "sparql"},
        )

    def test_asset_activation_blocked_shape(self):
        self._assert_envelope(
            "ASSET_ACTIVATION_BLOCKED",
            "Cannot activate asset: requirements not met.",
            409,
            {"blocker_code": "COMPLIANCE_SCAN_PENDING"},
        )

    def test_request_id_is_unique(self):
        # the request id travels in the X-Request-ID header (W12.5)
        r1 = format_error_response("CODE1", "msg", 400, request_id="req-a")
        r2 = format_error_response("CODE2", "msg", 400, request_id="req-b")
        assert r1["X-Request-ID"] != r2["X-Request-ID"]
        assert r1["X-Request-ID"] == "req-a"


class TestExceptionHandlerNoLeak(TestCase):
    """W1.16 — 5xx envelopes never surface ``str(exc)``; typed 4xx
    business messages are preserved; the canonical error-code precedence
    (nested domain code > exc.code > status map) is honored."""

    def _handler(self, exc):
        from rest_framework.test import APIRequestFactory

        from hub.apps.api.exceptions import custom_exception_handler

        request = APIRequestFactory().get("/api/v1/anything/")
        return custom_exception_handler(exc, {"request": request})

    def test_unhandled_exception_message_is_generic(self):
        resp = self._handler(
            Exception("SELECT * FROM top_secret_table WHERE api_key='live'")
        )
        assert resp.status_code == 500
        assert resp.data["error"]["message"] == "Internal server error"
        assert "top_secret_table" not in str(resp.data)

    def test_sql_error_like_exception_no_leak(self):
        resp = self._handler(
            RuntimeError(
                "FATAL: password authentication failed for user 'postgres'"
            )
        )
        assert resp.status_code == 500
        assert "password" not in str(resp.data)

    def test_typed_4xx_message_preserved(self):
        from rest_framework.exceptions import PermissionDenied

        resp = self._handler(PermissionDenied("Tenant plan lacks marketplace access"))
        assert resp.status_code == 403
        assert (
            resp.data["error"]["message"] == "Tenant plan lacks marketplace access"
        )

    def test_dict_form_domain_code_precedence(self):
        from rest_framework.exceptions import ValidationError as DRFValidationError

        resp = self._handler(
            DRFValidationError({"host": ["DATABRICKS_HOST_NOT_ALLOWED"]})
        )
        assert resp.data["error"]["code"] == "DATABRICKS_HOST_NOT_ALLOWED"

    # ── W10.3 (round-3 re-audit): the pre-fix handler ordered the
    # `.message` / string-`.detail` branches BEFORE the 5xx guard, so
    # repo-defined service exceptions (environment text by construction)
    # leaked verbatim — the plain-Exception pins above never covered
    # those shapes.

    def test_message_attr_exception_redacted_at_5xx(self):
        """A repo-shaped exception carrying ``.message`` (warehouses /
        core-services / integrations errors) must not leak it at 5xx."""

        class ServiceError(Exception):
            def __init__(self, message):
                self.message = message

        resp = self._handler(
            ServiceError(
                "connection to postgres://user:livepass@internal failed"
            )
        )
        assert resp.status_code == 500
        assert resp.data["error"]["message"] == "Internal server error"
        assert "livepass" not in str(resp.data)

    def test_string_detail_exception_redacted_at_5xx(self):
        """A string ``.detail`` at 5xx must not reach ``details``."""

        class DetailError(Exception):
            def __init__(self, detail):
                self.detail = detail

        resp = self._handler(
            DetailError("host 10.0.0.7 refused the connection")
        )
        assert resp.status_code == 500
        assert "10.0.0.7" not in str(resp.data)
