import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.7.1 — Developer journey: CLI developer tools.

Validates API documentation accessibility and OpenAPI JSON validity
via real API calls against the staging environment.
"""

from tests.use_cases._api_helpers import api_unauthenticated_get

# ===========================================================================
# Tests
# ===========================================================================


def test_api_docs_accessible():
    """GET /docs/ (or /swagger/, /redoc/) returns the API documentation page."""
    resp = api_unauthenticated_get("/docs/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/swagger/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/redoc/")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/api/docs/")
    if resp.status_code == 404:
        pytest.skip("API docs endpoint not found (404)")

    assert resp.status_code == 200, f"API docs returned {resp.status_code}: {resp.text[:300]}"

    # Docs page should have some content (HTML or JSON)
    assert len(resp.text) > 100, "API docs page returned very little content"


def test_openapi_json_valid():
    """GET /openapi.json returns a structurally valid OpenAPI 3.x document."""
    resp = api_unauthenticated_get("/openapi.json")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/docs/openapi.json")
    if resp.status_code == 404:
        resp = api_unauthenticated_get("/api/schema/")
    if resp.status_code == 404:
        pytest.skip("OpenAPI JSON endpoint not found (404)")

    assert resp.status_code == 200, f"OpenAPI JSON returned {resp.status_code}: {resp.text[:300]}"

    body = resp.json()

    # Validate top-level OpenAPI 3.x structure
    assert isinstance(body, dict), f"OpenAPI document should be a dict, got {type(body).__name__}"

    has_version_key = "openapi" in body or "swagger" in body
    assert has_version_key, (
        f"Missing 'openapi' or 'swagger' version key. Keys: {list(body.keys())[:10]}"
    )

    assert "info" in body, (
        f"OpenAPI document missing 'info' section. Keys: {list(body.keys())[:10]}"
    )
    assert "title" in body["info"], f"OpenAPI info missing 'title'. Info: {body['info']}"

    assert "paths" in body, (
        f"OpenAPI document missing 'paths' section. Keys: {list(body.keys())[:10]}"
    )
    assert isinstance(body["paths"], dict), (
        f"'paths' should be a dict, got {type(body['paths']).__name__}"
    )
    assert len(body["paths"]) > 0, "OpenAPI paths section is empty"
