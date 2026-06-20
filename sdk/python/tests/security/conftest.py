"""
Pytest collection hook for security integration tests.

Auto-skips security tests that require a live Meshant API when the
API is unreachable.  Tests that do NOT depend on the API
(test_tls_verification.py, test_dependency_audit.py) are always
collected regardless of API reachability.

Set ``MESHANT_FORCE_INTEGRATION=1`` to bypass the skip and force-run
all tests.
"""

import os

import pytest
import requests

# Files that do not require the live API — never auto-skip these.
_API_INDEPENDENT_FILES = {
    "test_tls_verification.py",
    "test_dependency_audit.py",
}


def _api_is_reachable(url: str) -> bool:
    try:
        response = requests.get(url, timeout=5)
    except requests.RequestException:
        return False
    return response.status_code < 500


def _get_default_api_url() -> str:
    """Return the default API URL, honoring API_TEST_PORT."""
    port = os.environ.get("API_TEST_PORT", "8001")
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
            f"Meshant API not reachable at {api_root}. Security integration "
            "tests require a live backend; start docker compose or set "
            "MESHANT_FORCE_INTEGRATION=1 to override."
        )
    )
    for item in items:
        fspath = str(item.fspath)
        # Never skip tests that don't need the API
        filename = os.path.basename(fspath)
        if filename in _API_INDEPENDENT_FILES:
            continue
        if any(d in fspath for d in ("/tests/security/")):
            item.add_marker(skip_marker)
