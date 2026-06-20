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
