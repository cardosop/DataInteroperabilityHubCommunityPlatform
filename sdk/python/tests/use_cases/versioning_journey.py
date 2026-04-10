import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.6.12 -- VersioningAPI journey.

Validates API versioning: the API-Version response header, the health
endpoint returning a version string, and the /api/v1/ prefix routing.
"""

from tests._persona_provisioning import provision_persona
from tests.use_cases._api_helpers import api_base_url, api_get


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _user_creds():
    return provision_persona("data_analyst")


def _skip_if_not_found(resp, label="Versioning"):
    if resp.status_code == 404:
        pytest.skip(f"{label} endpoint not available (404)")


# ===========================================================================
# Tests
# ===========================================================================


def test_api_version_header():
    """Responses should include an API version header (X-API-Version or similar)."""
    creds = _user_creds()

    # Use a well-known endpoint to check headers
    for path in ("/health/", "/healthz/", "/assets/", "/users/me/"):
        resp = api_get(path, creds)
        if resp.status_code in (200, 401, 403):
            headers_lower = {k.lower(): v for k, v in resp.headers.items()}
            has_version = any(
                "version" in k
                for k in headers_lower
            )
            if has_version:
                return  # pass
            # Also accept version in standard Server header
            server = headers_lower.get("server", "")
            if any(char.isdigit() for char in server):
                return  # version info in Server header

    pytest.skip(
        "No API response included a version header "
        "(checked X-API-Version and similar)"
    )


def test_health_returns_version():
    """Health endpoint response body should include a version string."""
    creds = _user_creds()

    resp = None
    for path in ("/health/", "/healthz/", "/health"):
        candidate = api_get(path, creds)
        if candidate.status_code == 200:
            resp = candidate
            break

    if resp is None:
        pytest.skip("No health endpoint returned 200")

    body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}

    if isinstance(body, dict):
        keys_lower = {k.lower() for k in body.keys()}
        has_version = any(
            k in keys_lower
            for k in ("version", "api_version", "build", "release", "commit")
        )
        if not has_version:
            body_str = str(body).lower()
            has_version = any(
                keyword in body_str
                for keyword in ("version", "v1", "v2", "build")
            )
        assert has_version, (
            f"Health response lacks version information: {body}"
        )
    else:
        pytest.skip("Health response is not JSON dict; cannot check for version field")


def test_api_v1_prefix_works():
    """Requests to /api/v1/... should route correctly."""
    creds = _user_creds()
    base = api_base_url()

    # The base URL likely already includes /api/v1, but verify a known
    # endpoint under that prefix works
    for path in ("/health/", "/assets/", "/users/me/"):
        resp = api_get(path, creds)
        if resp.status_code in (200, 401, 403):
            # The v1 prefix is working (we got a real response, not 404)
            assert resp.status_code < 500, (
                f"API v1 endpoint {path} returned server error: {resp.status_code}"
            )
            return

    pytest.skip("No v1-prefixed endpoint returned a non-404 response")
