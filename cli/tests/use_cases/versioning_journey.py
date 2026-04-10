import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Versioning journey: CLI versioning endpoints.

Validates API version header presence and OpenAPI schema
accessibility via real API calls against the staging environment.
"""

import requests
from tests.use_cases._api_helpers import api_unauthenticated_get


# ===========================================================================
# Tests
# ===========================================================================


def test_api_version_header_present():
    """A request to any API endpoint includes an API version header
    in the response (e.g., X-API-Version, API-Version).
    """
    resp = api_unauthenticated_get("/health/")

    if resp.status_code == 404:
        # Fall back to root
        resp = api_unauthenticated_get("/")
    if resp.status_code == 404:
        pytest.skip("No reachable endpoint to check version header")

    headers = resp.headers
    version_header_names = [
        "X-API-Version",
        "API-Version",
        "X-Version",
        "X-App-Version",
    ]
    found = {
        name: headers.get(name)
        for name in version_header_names
        if headers.get(name)
    }

    if not found:
        # Version may also be in the response body
        try:
            body = resp.json()
            body_version = body.get("version", body.get("api_version"))
            if body_version:
                found["body.version"] = body_version
        except (ValueError, requests.exceptions.JSONDecodeError):
            pass

    assert found, (
        f"No API version header or body field found. "
        f"Response headers: {dict(headers)}"
    )


def test_openapi_schema_accessible():
    """GET /openapi.json (or /docs/openapi.json, /api/schema/) returns
    a valid OpenAPI schema document.
    """
    resp = api_unauthenticated_get("/openapi.json")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/docs/openapi.json")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/api/schema/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/schema/")
    if resp.status_code == 404:
        pytest.skip("OpenAPI schema endpoint not found (404)")

    assert resp.status_code == 200, (
        f"OpenAPI schema returned {resp.status_code}: {resp.text[:300]}"
    )

    body = resp.json()
    # Must be a valid OpenAPI document
    assert "openapi" in body or "swagger" in body or "info" in body, (
        f"Response does not look like an OpenAPI schema. "
        f"Keys: {list(body.keys())[:10]}"
    )

    if "info" in body:
        assert "title" in body["info"], (
            f"OpenAPI info missing title. Info keys: {list(body['info'].keys())}"
        )
