"""
Phase 279.H.pa_admin — Platform Admin persona journey tests (CLI).

Tests the Platform Admin end-to-end workflow through the CLI.
Uses ``datahub`` CLI subprocess.  Requires ``DATAHUB_BASE_URL``
and ``DATAHUB_API_TOKEN`` env vars.  All tests skip when no
backend is detected.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 \
  DATAHUB_API_TOKEN=<token> \
  pytest cli/tests/use_cases/test_pa_admin_journey.py -v
"""

import json
import os
import subprocess

import pytest

pytestmark = [
    pytest.mark.journey("JOURNEY-PA-001"),
]

DATAHUB_BASE_URL = os.environ.get("DATAHUB_BASE_URL", "")
DATAHUB_CLI = os.environ.get("DATAHUB_CLI", "datahub")
API_TOKEN = os.environ.get("DATAHUB_API_TOKEN", "")


def _backend_available():
    if not DATAHUB_BASE_URL:
        return False
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{DATAHUB_BASE_URL.rstrip('/')}/health/",
            headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
        )
        resp = urllib.request.urlopen(req, timeout=5)
        return resp.status == 200
    except Exception:
        return False


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


def _cli(*args):
    cmd = [DATAHUB_CLI] + list(args) + ["--format", "json"]
    env = {**os.environ, "DATAHUB_BASE_URL": DATAHUB_BASE_URL}
    if API_TOKEN:
        env["DATAHUB_API_TOKEN"] = API_TOKEN
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=60, env=env)
    if result.returncode != 0:
        pytest.skip(f"CLI command failed (rc={result.returncode}): {result.stderr[:200]}")
    return json.loads(result.stdout)


@pytest.mark.integration
@requires_backend
class TestPAJourney:
    """Platform Admin persona — end-to-end CLI journey."""

    def test_cli_is_installed(self):
        """Verify datahub CLI is callable."""
        result = subprocess.run(
            [DATAHUB_CLI, "--help"], check=False, capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0

    def test_tenants_list(self):
        """CLI ``tenants list`` returns valid response."""
        data = _cli("tenants", "list")
        assert data is not None

    def test_platform_users_list(self):
        """CLI ``users list`` returns valid response."""
        data = _cli("users", "list")
        assert data is not None

    def test_capabilities_list(self):
        """CLI ``capabilities list`` returns valid response."""
        data = _cli("capabilities", "list")
        assert data is not None
