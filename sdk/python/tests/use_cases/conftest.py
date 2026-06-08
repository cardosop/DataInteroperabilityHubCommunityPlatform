"""
Pytest fixtures for CLI e2e tests.

Mirrors ``tests/integration/conftest.py``: auto-skips e2e tests when no live
Meshant API is reachable. e2e tests run a real CLI against a real backend
and have no business failing on dev boxes that don't run docker compose.
Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass.
"""
import os

import pytest
import requests


def _api_is_reachable(url: str) -> bool:
    try:
        response = requests.get(url, timeout=2)
    except requests.RequestException:
        return False
    return response.status_code < 500


def _get_default_api_url() -> str:
    """Return the default API URL, honoring API_TEST_PORT for host-based tests."""
    port = os.environ.get("API_TEST_PORT", "8000")
    return f"http://localhost:{port}/api/v1"


def pytest_collection_modifyitems(config, items):  # noqa: ARG001
    if os.environ.get("MESHANT_FORCE_INTEGRATION") == "1":
        return
    api_url = os.environ.get("MESHANT_API_URL") or _get_default_api_url()
    api_root = api_url.rsplit("/api/v1", 1)[0] or api_url
    if _api_is_reachable(api_root):
        return
    skip_marker = pytest.mark.skip(
        reason=(
            f"Meshant API not reachable at {api_root}. CLI e2e tests "
            "require a live backend; start docker compose or set "
            "MESHANT_FORCE_INTEGRATION=1 to override."
        )
    )
    for item in items:
        fspath = str(item.fspath)
        if any(d in fspath for d in ("/tests/e2e/", "/tests/use_cases/", "/tests/security/")):
            item.add_marker(skip_marker)


# ── Token lifecycle helper for use-case / journey tests ────────────────
# These tests import ``API_TOKEN = os.environ.get("DATAHUB_API_TOKEN", "")``
# at module level, which captures whatever token was set during
# pytest_sessionstart.  When persona provisioning later bumps the user's
# token_version (via ensure-e2e-users self-heal), that module-level
# variable is STALE and the tests see 401 "Token has been invalidated".
#
# This fixture runs before each use-case test CLASS and validates the
# token.  If it's gone stale, a fresh login is performed and all env
# vars (DATAHUB_API_TOKEN, TEST_API_KEY, DATAHUB_API_KEY) are updated
# so the next test picks up a valid credential.
#
# The check is a single ``GET /api/v1/auth/me/`` — typically 50-200 ms
# on a local test stack.  We scope it to the CLASS rather than each
# function so we pay that cost ~17 times instead of ~130 times.

@pytest.fixture(scope="class", autouse=True)
def _refresh_test_token_if_stale():
    """Auto-validate token before each test class; refresh if invalid."""
    from tests.conftest import get_api_key, _token_valid

    token = os.environ.get("DATAHUB_API_TOKEN") or os.environ.get("TEST_API_KEY") or os.environ.get("DATAHUB_API_KEY")
    if token and not _token_valid(token):
        # Token is stale — force fresh login and update all env vars.
        # Pop auto-provisioning cache keys so get_api_key() performs a
        # full login rather than returning the (now-invalid) cached value.
        for _key in ("_AUTO_PROVISIONED_API_KEY", "_AUTO_PROVISIONED_REFRESH_TOKEN"):
            os.environ.pop(_key, None)
        get_api_key()
    # If there's no token at all, get_api_key() at session-start should
    # have set one — but guard against the edge case anyway.
    elif not token:
        get_api_key()
    yield
