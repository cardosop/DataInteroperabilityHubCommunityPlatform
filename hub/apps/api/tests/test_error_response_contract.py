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
        assert "error" in data, f"Missing 'error' key in {data}"
        err = data["error"]
        assert err["code"] == code
        assert err["message"] == message
        assert err["http_status"] == http_status
        assert "request_id" in err
        assert "timestamp" in err
        if details:
            assert err.get("details") == details

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
        r1 = format_error_response("CODE1", "msg", 400)
        r2 = format_error_response("CODE2", "msg", 400)
        assert r1.data["error"]["request_id"] != r2.data["error"]["request_id"]


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
