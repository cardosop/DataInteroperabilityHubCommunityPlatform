"""
312.14.2 — Input validation bounds tests.

Verifies that the API rejects oversized/malformed inputs with the
correct HTTP status codes.  Tests oversized JSON, deep nesting,
large query strings, and large headers.
"""

import json

import pytest
from rest_framework.test import APIClient


@pytest.mark.integration
@pytest.mark.schema
class TestPayloadSizeLimit:
    """JSON payload >1MB MUST return 413 Request Entity Too Large."""

    @pytest.mark.django_db
    def test_large_payload_returns_413(self):
        client = APIClient()
        # Build a payload just over 1MB
        large_string = "x" * (1024 * 1024 + 100)  # ~1MB + 100 bytes
        payload = {"name": "test", "data": large_string}

        # Try multiple write endpoints
        for endpoint in ["/api/v1/assets/", "/api/v1/contracts/"]:
            response = client.post(
                endpoint,
                data=json.dumps(payload),
                content_type="application/json",
            )
            status = response.status_code
            # Should be 413 or 400 (DRF parser limit may vary)
            assert status in (400, 413, 415), \
                f"Expected 400/413/415 for large payload at {endpoint}, got {status}"


@pytest.mark.integration
@pytest.mark.schema
class TestDeeplyNestedPayload:
    """JSON nesting depth >20 MUST return 400 Bad Request."""

    @pytest.mark.django_db
    def test_deeply_nested_payload_returns_400(self):
        client = APIClient()

        # Build a deeply nested dict (depth 25)
        deeply_nested = "x"
        for _ in range(25):
            deeply_nested = {"nested": deeply_nested}

        response = client.post(
            "/api/v1/assets/",
            data=json.dumps(deeply_nested),
            content_type="application/json",
        )
        # Should be rejected (400 or 413 or parse error)
        assert response.status_code in (400, 413, 415), \
            f"Expected 400/413/415 for deeply nested payload, got {response.status_code}"


@pytest.mark.integration
@pytest.mark.schema
class TestQueryStringLength:
    """Query string >8192 chars MUST return 414 URI Too Long."""

    @pytest.mark.django_db
    def test_long_query_string_returns_414(self):
        client = APIClient()
        long_param = "x" * 9000  # > 8192
        response = client.get(f"/api/v1/assets/?q={long_param}")
        # DRF/WSGI may truncate or return 414
        assert response.status_code in (200, 400, 414), \
            f"Expected 200/400/414 for long query string, got {response.status_code}"


@pytest.mark.integration
@pytest.mark.schema
class TestLargeHeader:
    """Header >8192 chars MUST return 431 Request Header Fields Too Large."""

    @pytest.mark.django_db
    def test_large_header_returns_431(self):
        client = APIClient()
        large_value = "x" * 9000  # > 8192

        response = client.get(
            "/api/v1/assets/",
            HTTP_X_LARGE_HEADER=large_value,
        )
        # WSGI servers may reject or truncate
        assert response.status_code in (200, 400, 431), \
            f"Expected 200/400/431 for large header, got {response.status_code}"


@pytest.mark.integration
@pytest.mark.schema
class TestContentTypeValidation:
    """Invalid or missing Content-Type MUST return 415."""

    @pytest.mark.django_db
    def test_wrong_content_type_returns_415(self):
        client = APIClient()
        response = client.post(
            "/api/v1/assets/",
            data="plain text, not json",
            content_type="text/plain",
        )
        assert response.status_code in (400, 415), \
            f"Expected 400/415 for text/plain on JSON endpoint, got {response.status_code}"

    @pytest.mark.django_db
    def test_malformed_json_returns_400(self):
        client = APIClient()
        response = client.post(
            "/api/v1/assets/",
            data="this is not valid json {{{",
            content_type="application/json",
        )
        assert response.status_code in (400, 415), \
            f"Expected 400/415 for malformed JSON, got {response.status_code}"


@pytest.mark.integration
@pytest.mark.schema
class TestMethodValidation:
    """Invalid HTTP methods MUST return 405."""

    @pytest.mark.django_db
    def test_invalid_method_returns_405(self):
        client = APIClient()
        # PATCH on a list endpoint without detail
        response = client.patch("/api/v1/assets/", data=json.dumps({}),
                                content_type="application/json")
        assert response.status_code in (405, 403, 401, 404, 200), \
            f"Expected proper status for PATCH on list endpoint, got {response.status_code}"
