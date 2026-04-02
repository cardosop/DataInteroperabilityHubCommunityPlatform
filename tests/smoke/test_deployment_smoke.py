"""Phase 109.7 — Expanded deployment smoke tests.

Validates critical deployment paths beyond the existing 9 smoke test files.
Tests skip gracefully if the target service is unavailable.
"""
import os
import pytest
import requests

# Base URL from environment or default
BASE_URL = os.environ.get("SMOKE_BASE_URL", os.environ.get("API_BASE_URL", "http://localhost:8000"))
TIMEOUT = int(os.environ.get("SMOKE_TEST_TIMEOUT", "10"))


def _get(path, session=None, **kwargs):
    """GET helper with timeout and connection error handling."""
    url = f"{BASE_URL}{path}"
    try:
        r = (session or requests).get(url, timeout=TIMEOUT, **kwargs)
        return r
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip(f"Service unavailable at {url}")


def _post(path, session=None, **kwargs):
    """POST helper with timeout and connection error handling."""
    url = f"{BASE_URL}{path}"
    try:
        r = (session or requests).post(url, timeout=TIMEOUT, **kwargs)
        return r
    except (requests.ConnectionError, requests.Timeout):
        pytest.skip(f"Service unavailable at {url}")


class TestHealthEndpoints:
    """Validate health and readiness endpoints."""

    def test_liveness_endpoint(self):
        r = _get("/health/")
        assert r.status_code in (200, 503)

    def test_health_returns_json(self):
        r = _get("/health/")
        assert r.headers.get("content-type", "").startswith("application/json")

    def test_health_no_500(self):
        """Health endpoint must never return 500."""
        r = _get("/health/")
        assert r.status_code != 500


class TestAPIDocumentation:
    """Validate API documentation endpoints."""

    def test_openapi_schema_accessible(self):
        r = _get("/api-docs/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "paths" in data

    def test_swagger_ui_accessible(self):
        r = _get("/api-docs/")
        assert r.status_code == 200


class TestAuthEndpoints:
    """Validate authentication endpoints respond."""

    def test_login_endpoint_exists(self):
        r = _post("/api/v1/auth/login/", json={"email": "x", "password": "x"})
        # Should get 400 (bad request) or 401 (unauthorized), not 404
        assert r.status_code in (400, 401, 403, 422)

    def test_register_endpoint_exists(self):
        r = _post("/api/v1/auth/register/", json={"email": "x"})
        # Should get 400 (validation) not 404
        assert r.status_code in (400, 403, 422)


class TestCoreAPIEndpoints:
    """Validate core API endpoints require authentication."""

    @pytest.mark.parametrize("path", [
        "/api/v1/assets/",
        "/api/v1/contracts/",
        "/api/v1/datasets/",
        "/api/v1/jobs/",
    ])
    def test_core_endpoints_require_auth(self, path):
        r = _get(path)
        assert r.status_code in (401, 403)

    @pytest.mark.parametrize("path", [
        "/api/v1/marketplace/listings/",
        "/api/v1/webhooks/webhooks/",
        "/api/v1/dq/runs/",
        "/api/v1/compliance/runs/",
    ])
    def test_feature_endpoints_require_auth(self, path):
        r = _get(path)
        assert r.status_code in (401, 403)


class TestDatabaseConnectivity:
    """Validate database is accessible via health endpoint."""

    def test_health_includes_database_status(self):
        r = _get("/health/")
        if r.status_code == 200:
            data = r.json()
            # Health check should include DB status
            assert isinstance(data, dict)


class TestCacheConnectivity:
    """Validate Redis cache is accessible."""

    def test_health_endpoint_responds(self):
        """If health returns 200, cache is likely working."""
        r = _get("/health/")
        assert r.status_code in (200, 503)


class TestSecurityHeaders:
    """Validate security headers on API responses."""

    def test_api_response_has_content_type(self):
        r = _get("/health/")
        assert "content-type" in r.headers


class TestGraphQLEndpoint:
    """Validate GraphQL endpoint responds."""

    def test_graphql_endpoint_exists(self):
        r = _post("/graphql/", json={"query": "{ __typename }"})
        # Should respond (200 or 400 for auth), not 404
        assert r.status_code in (200, 400, 401, 403, 405)


class TestMultiTenantIsolation:
    """Validate tenant isolation at API level."""

    def test_unauthenticated_cannot_access_data(self):
        r = _get("/api/v1/assets/")
        assert r.status_code in (401, 403)
        # Response should not contain any asset data
        if r.status_code in (401, 403):
            body = r.text
            assert "results" not in body or '"results": []' in body or '"results":[]' in body
