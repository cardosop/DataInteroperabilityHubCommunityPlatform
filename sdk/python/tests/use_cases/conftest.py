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
    from tests.conftest import _token_valid, get_api_key

    token = (
        os.environ.get("DATAHUB_API_TOKEN")
        or os.environ.get("TEST_API_KEY")
        or os.environ.get("DATAHUB_API_KEY")
    )
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


# ── Proactive E2E user self-heal ─────────────────────────────────────────
# The auth lifecycle tests (test_auth_lifecycle.py) invalidate ALL cached
# JWT tokens by calling POST /auth/logout/ for every persona.  This forces
# every subsequent provision_persona() call to re-login.  If the re-login
# finds the E2E user's password out of sync (common after container
# restarts), the self-heal runs mid-suite under load and occasionally fails
# (timeout, connection refused), causing provision_persona to skip.
#
# This session-scoped fixture runs ONCE before any use-case test and
# proactively heals the three most critical E2E users (tenant_admin,
# data_mesh_domain_owner, auditor).  If their logins succeed, the
# passwords are correct and subsequent provision_persona calls won't
# need mid-suite self-heal.


@pytest.fixture(scope="session", autouse=True)
def _proactively_heal_e2e_users():
    """Ensure critical E2E users have correct passwords before test suite."""
    import requests as _rq

    port = os.environ.get("API_TEST_PORT", "8000")
    base = os.environ.get("MESHANT_API_URL", f"http://localhost:{port}/api/v1")
    e2e_secret = os.environ.get("E2E_TEST_SECRET", "e2e-test-secret-for-local-dev")

    # Only heal if the API is reachable (skip during collection on
    # machines where the test stack isn't running).
    try:
        _rq.get(base.rsplit("/api/v1", 1)[0] + "/health/", timeout=3)
    except _rq.RequestException:
        return  # API not available — tests will skip via collection hook

    for email in (
        "e2e_admin@example.com",  # used by invitation + tenant-switch tests
        "e2e_dmo@example.com",  # used by quota + marketplace tests
        "e2e_auditor@example.com",  # used by authz enforcement tests
    ):
        try:
            _rq.post(
                f"{base}/test/ensure-e2e-users/",
                json={"email": email},
                headers={"X-E2E-Token": e2e_secret},
                timeout=15,
            )
        except _rq.RequestException:
            continue  # best-effort; don't fail collection

    yield
