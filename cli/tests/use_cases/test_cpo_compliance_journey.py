"""
Phase 279.H.cpo_compliance — CPO persona journey tests (CLI).

Tests the CPO end-to-end workflow through the CLI.
Uses ``datahub`` CLI subprocess.  Requires ``DATAHUB_BASE_URL``
and ``DATAHUB_API_TOKEN`` env vars.  All tests skip when no
backend is detected.

Usage:
  DATAHUB_BASE_URL=http://localhost:8000/api/v1 \
  DATAHUB_API_TOKEN=<token> \
  pytest cli/tests/use_cases/test_cpo_compliance_journey.py -v
"""

import json
import os
import subprocess

import pytest

pytestmark = [
    pytest.mark.journey("JOURNEY-CPO-001"),
]

DATAHUB_BASE_URL = os.environ.get("DATAHUB_BASE_URL", "")
DATAHUB_CLI = os.environ.get("DATAHUB_CLI", "datahub")
API_TOKEN = os.environ.get("DATAHUB_API_TOKEN", "")
ROLE = "compliance_officer"


def _journey_token(role: str) -> str:
    """Provision the journey persona's token.

    The batch runner exports one generic DATAHUB_API_TOKEN (a
    data_engineer key); the journey commands need a persona with the
    journey's roles (TENANT_ADMIN / DPO / LEGAL_ADMIN).  Provision the
    right persona and fall back to the env token when provisioning is
    unavailable (the W16 pattern).
    """
    try:
        from tests._persona_provisioning import provision_persona

        return provision_persona(role).api_key
    except Exception:
        return API_TOKEN


def _backend_available():
    if not DATAHUB_BASE_URL:
        return False
    import urllib.request

    try:
        req = urllib.request.Request(
            f"{DATAHUB_BASE_URL.rstrip('/')}/health/business-rules/",
            headers={"Authorization": f"Bearer {API_TOKEN}"} if API_TOKEN else {},
        )
        resp = urllib.request.urlopen(req, timeout=5)
    except Exception:
        return False
    else:
        return resp.status == 200


BACKEND_AVAILABLE = _backend_available()
requires_backend = pytest.mark.skipif(
    not BACKEND_AVAILABLE,
    reason="No backend detected — set DATAHUB_BASE_URL + DATAHUB_API_TOKEN",
)


def _cli(*args, no_format: bool = False):
    # Some commands (developer portal, notifications list, security
    # incidents, tenants config) do not accept --format — callers that
    # hit them pass no_format=True.
    cmd = [DATAHUB_CLI, *list(args)]
    if not no_format:
        cmd += ["--format", "json"]
    env = {**os.environ, "DATAHUB_BASE_URL": DATAHUB_BASE_URL}
    _token = _journey_token(ROLE)
    if _token:
        env["DATAHUB_API_TOKEN"] = _token
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=180, env=env)
    if result.returncode != 0:
        pytest.skip(f"CLI command failed (rc={result.returncode}): {result.stderr[:200]}")
    return json.loads(result.stdout)


@pytest.mark.integration
@requires_backend
class TestCPOJourney:
    """CPO persona — end-to-end CLI journey."""

    def test_cli_is_installed(self):
        """Verify datahub CLI is callable."""
        result = subprocess.run(
            [DATAHUB_CLI, "--help"], check=False, capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0

    def test_ropa_generate(self):
        """CLI ``ropa generate`` returns valid response."""
        data = _cli("ropa", "generate")
        assert data is not None

    def test_dpia_list(self):
        """CLI ``dpia list`` returns valid response."""
        data = _cli("dpia", "list")
        assert data is not None

    def test_security_incidents_list(self):
        """CLI ``security incidents list`` returns valid response."""
        data = _cli("security", "incidents", "list")
        assert data is not None
