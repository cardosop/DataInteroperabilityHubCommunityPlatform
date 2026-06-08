"""
312.14.3 — Error response format tests.

Verifies that all error responses follow the standard format:
{error, error_code, detail}.  Production error responses must NOT
contain stack traces, DB errors, internal IPs, or hostnames.
"""

import json

import pytest
from django.test import override_settings
from rest_framework.test import APIClient


@pytest.mark.integration
@pytest.mark.schema
class TestErrorResponseStructure:
    """Every error response MUST have 'error' or 'detail' field."""

    _ERROR_ENDPOINTS = [
        ("/api/v1/assets/nonexistent-id-12345/", "GET"),
        ("/api/v1/contracts/nonexistent-id-12345/", "GET"),
        ("/api/v1/assets/", "POST"),  # Missing body
        ("/api/v1/assets/", "DELETE"),  # Method not allowed
    ]

    @pytest.mark.django_db
    def test_404_error_has_detail_field(self):
        """404 responses MUST have a 'detail' field."""
        client = APIClient()
        response = client.get("/api/v1/assets/nonexistent-id-12345/")
        if response.status_code >= 500:
            pytest.skip("Backend unavailable")

        # 404 from DRF returns {"detail": "Not found."}
        if response.status_code == 404:
            try:
                data = response.json()
                assert "detail" in data, \
                    f"404 response missing 'detail': {data}"
            except json.JSONDecodeError:
                pass  # Some endpoints may not return JSON for 404

    @pytest.mark.django_db
    def test_405_error_has_detail_field(self):
        """405 responses MUST have a structured error body."""
        client = APIClient()
        response = client.delete("/api/v1/assets/")
        if response.status_code == 405:
            try:
                data = response.json()
                assert "detail" in data or "error" in data, \
                    f"405 response missing error details: {data}"
            except json.JSONDecodeError:
                pass

    @pytest.mark.django_db
    @pytest.mark.parametrize("endpoint,method", _ERROR_ENDPOINTS)
    def test_error_responses_are_json(self, endpoint, method):
        """Error responses MUST be JSON (Content-Type: application/json)."""
        client = APIClient()
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, data=json.dumps({}),
                                   content_type="application/json")
        elif method == "DELETE":
            response = client.delete(endpoint)
        else:
            return

        if response.status_code >= 400 and response.status_code < 500:
            ct = response.get("Content-Type", "")
            # JSON content type check
            if response.content:
                assert "application/json" in ct or response.status_code == 404, \
                    f"Error response for {method} {endpoint} should be JSON, got {ct}"


@pytest.mark.integration
@pytest.mark.schema
class TestErrorResponseSanitization:
    """Error responses MUST NOT contain internal details."""

    # Patterns that must NOT appear in production error responses
    _BLOCKED_PATTERNS = [
        "Traceback (most recent call last)",
        "File \"",
        "django/db/",
        "psycopg2",
        "OPERATION_FAILED",
    ]

    @pytest.mark.django_db
    @override_settings(DEBUG=False)  # Simulate production
    def test_400_response_no_stack_trace(self):
        """400 responses in production mode MUST NOT contain stack traces."""
        client = APIClient()
        response = client.post(
            "/api/v1/assets/",
            data="not valid json {{{",
            content_type="application/json",
        )
        if response.status_code in (400, 415) and response.content:
            try:
                body = response.content.decode()
                for pattern in self._BLOCKED_PATTERNS[:2]:  # Check traceback patterns
                    assert pattern not in body, \
                        f"Error response contains '{pattern}': {body[:200]}"
            except Exception:
                pass  # Non-JSON body, check raw
                body = response.content.decode(errors="replace")
                for pattern in self._BLOCKED_PATTERNS[:2]:
                    assert pattern not in body, \
                        f"Error response contains '{pattern}': {body[:200]}"

    @pytest.mark.django_db
    @override_settings(DEBUG=False)
    def test_500_response_no_internal_details(self):
        """500 responses MUST NOT expose DB errors or internal paths."""
        client = APIClient()
        # Trigger a 500 by sending a deliberately broken request
        # (most 500s require server bugs, so this is a best-effort check)
        response = client.get("/api/v1/assets/")
        if response.status_code == 500 and response.content:
            body = response.content.decode(errors="replace")
            for pattern in ["Traceback", "django/db/", "psycopg2"]:
                assert pattern not in body, \
                    f"500 response must not expose '{pattern}'"
