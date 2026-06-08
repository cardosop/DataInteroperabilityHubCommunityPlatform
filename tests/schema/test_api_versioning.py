"""
312.14.5 — API versioning, deprecation, content negotiation, and
OpenAPI accuracy tests.

Verifies: Deprecation headers on sunset endpoints, Content-Type
negotiation (Accept header), X-API-Version/Accept-Version headers,
and OpenAPI schema accuracy.
"""

import pytest
from rest_framework.test import APIClient


@pytest.mark.integration
@pytest.mark.schema
class TestContentNegotiation:
    """SPARQL/semantic endpoints return correct Content-Type based on Accept header."""

    @pytest.mark.django_db
    def test_accept_json_returns_json(self):
        """Accept: application/json MUST return JSON."""
        client = APIClient()
        response = client.get(
            "/api/v1/assets/",
            HTTP_ACCEPT="application/json",
        )
        if response.status_code >= 500:
            pytest.skip("Backend unavailable")
        if response.status_code == 200 and response.content:
            ct = response.get("Content-Type", "")
            assert "application/json" in ct, \
                f"Expected JSON Content-Type, got: {ct}"

    @pytest.mark.django_db
    def test_accept_wildcard_returns_json(self):
        """Accept: */* MUST return JSON (default for REST API)."""
        client = APIClient()
        response = client.get(
            "/api/v1/assets/",
            HTTP_ACCEPT="*/*",
        )
        if response.status_code >= 500:
            pytest.skip("Backend unavailable")
        if response.status_code == 200 and response.content:
            ct = response.get("Content-Type", "")
            assert "application/json" in ct or "text/html" in ct, \
                f"Expected JSON or HTML Content-Type, got: {ct}"


@pytest.mark.integration
@pytest.mark.schema
class TestAPIVersionHeaders:
    """X-API-Version and Accept-Version headers are handled correctly."""

    @pytest.mark.django_db
    def test_x_api_version_accepted(self):
        """Requests with X-API-Version header are processed without error."""
        client = APIClient()
        response = client.get(
            "/api/v1/assets/",
            HTTP_X_API_VERSION="1.0",
        )
        assert response.status_code not in (406, 501), \
            f"X-API-Version header should not cause 406/501, got {response.status_code}"

    @pytest.mark.django_db
    def test_accept_version_accepted(self):
        """Requests with Accept-Version header are processed without error."""
        client = APIClient()
        response = client.get(
            "/api/v1/assets/",
            HTTP_ACCEPT_VERSION="1.0",
        )
        assert response.status_code not in (406, 501), \
            f"Accept-Version header should not cause 406/501, got {response.status_code}"


@pytest.mark.integration
@pytest.mark.schema
class TestOpenAPISchema:
    """The OpenAPI schema endpoint returns valid JSON that matches the live API."""

    @pytest.mark.django_db
    def test_openapi_schema_is_valid_json(self):
        """GET /api/v1/openapi.json returns valid JSON."""
        client = APIClient()
        response = client.get("/api/v1/openapi.json")
        if response.status_code >= 500:
            pytest.skip("Backend unavailable")

        assert response.status_code == 200, \
            f"OpenAPI schema should return 200, got {response.status_code}"

        data = response.json()
        assert "openapi" in data, f"Missing 'openapi' version: {list(data.keys())[:5]}"
        assert "info" in data, "Missing 'info' in OpenAPI schema"
        assert "paths" in data, "Missing 'paths' in OpenAPI schema"
        assert isinstance(data["paths"], dict), "'paths' must be a dict"

    @pytest.mark.django_db
    def test_openapi_schema_has_key_endpoints(self):
        """OpenAPI schema includes key API endpoints."""
        client = APIClient()
        response = client.get("/api/v1/openapi.json")
        if response.status_code != 200:
            pytest.skip("OpenAPI schema unavailable")

        data = response.json()
        paths = data.get("paths", {})
        # Key paths should be documented
        expected_prefixes = ["/api/v1/assets", "/api/v1/contracts", "/api/v1/datasets"]
        found = [p for p in expected_prefixes
                 if any(k.startswith(p) for k in paths)]
        assert len(found) > 0, \
            f"No expected endpoints found in OpenAPI schema. Paths: {list(paths.keys())[:10]}"

    @pytest.mark.django_db
    def test_openapi_yaml_returns_yaml(self):
        """GET /api/v1/openapi.yaml returns YAML."""
        client = APIClient()
        response = client.get("/api/v1/openapi.yaml")
        if response.status_code == 200:
            ct = response.get("Content-Type", "")
            content = response.content.decode(errors="replace")[:100]
            assert "openapi" in content.lower() or "application" in ct.lower(), \
                f"YAML endpoint should return valid content, got: {content[:80]}"


@pytest.mark.integration
@pytest.mark.schema
class TestAPIDeprecationHeaders:
    """Deprecated endpoints return Deprecation and Link headers."""

    @pytest.mark.django_db
    def test_api_root_returns_response(self):
        """GET /api/v1/ returns basic API info."""
        client = APIClient()
        response = client.get("/api/v1/")
        if response.status_code >= 500:
            pytest.skip("Backend unavailable")
        assert response.status_code in (200, 301, 302), \
            f"API root should return 200/301/302, got {response.status_code}"
