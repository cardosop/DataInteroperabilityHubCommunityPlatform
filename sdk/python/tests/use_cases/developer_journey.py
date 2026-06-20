import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.12 -- DeveloperAPI journey.

Validates developer-facing endpoints: API documentation, OpenAPI schema
availability, and schema validity.
"""

import json

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_get

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dev_creds():
    return provision_persona("data_analyst")


def _skip_if_not_found(resp, label="Developer"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


def _try_paths(creds, paths):
    """Try a list of paths and return the first non-404 response, or the last."""
    resp = None
    for path in paths:
        resp = api_get(path, creds)
        if resp.status_code != 404:
            return resp
    return resp


# ===========================================================================
# Tests
# ===========================================================================


def test_api_docs_endpoint():
    """An API documentation endpoint (Swagger/Redoc) is accessible."""
    creds = _dev_creds()
    resp = _try_paths(
        creds,
        [
            "/docs/",
            "/api/docs/",
            "/swagger/",
            "/redoc/",
            "/api/v1/docs/",
        ],
    )
    _skip_if_not_found(resp, "API docs")

    assert resp.status_code == 200, (
        f"API docs endpoint returned {resp.status_code}: {resp.text[:500]}"
    )


def test_openapi_schema_endpoint():
    """The OpenAPI schema endpoint returns a JSON or YAML schema."""
    creds = _dev_creds()
    resp = _try_paths(
        creds,
        [
            "/openapi.json",
            "/api/schema/",
            "/api/v1/schema/",
            "/schema/",
            "/openapi/",
        ],
    )
    _skip_if_not_found(resp, "OpenAPI schema")

    assert resp.status_code == 200, f"OpenAPI schema returned {resp.status_code}: {resp.text[:500]}"

    content_type = resp.headers.get("content-type", "")
    assert "json" in content_type or "yaml" in content_type or "yml" in content_type, (
        f"OpenAPI schema has unexpected content-type: {content_type}"
    )


def test_schema_is_valid_json():
    """The OpenAPI schema is parseable as valid JSON (if JSON endpoint)."""
    creds = _dev_creds()
    resp = _try_paths(
        creds,
        [
            "/openapi.json",
            "/api/schema/",
            "/api/v1/schema/",
            "/schema/",
        ],
    )
    _skip_if_not_found(resp, "OpenAPI schema")

    if resp.status_code != 200:
        pytest.skip(f"Schema endpoint returned {resp.status_code}")

    content_type = resp.headers.get("content-type", "")
    if "json" not in content_type:
        pytest.skip(f"Schema is not JSON (content-type: {content_type})")

    try:
        schema = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        pytest.fail(f"OpenAPI schema is not valid JSON: {exc}")

    # Basic OpenAPI structure checks
    assert isinstance(schema, dict), f"Schema root is not a dict: {type(schema)}"
    has_version = "openapi" in schema or "swagger" in schema or "info" in schema
    assert has_version, f"Schema missing openapi/swagger/info key: {list(schema.keys())[:10]}"
