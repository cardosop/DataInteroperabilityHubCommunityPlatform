"""
Phase 279.H.dev_portal — Developer persona journey tests (CLI).

Tests the Developer end-to-end workflow through the CLI.

CLI subprocesses authenticate through the shared journey helpers, which
provision a persona token (self-healing disk cache + /auth/me/
validation) rather than trusting a host-shell ``DATAHUB_API_TOKEN`` —
a stale exported token previously made every API command 401 and the
tests silently skipped (measured 2026-09-20).  All tests skip when no
backend is detected.
"""

import subprocess

import pytest
from tests.use_cases._journey_helpers import (
    DATAHUB_CLI_CMD,
    _cli,
    requires_backend,
)

pytestmark = [
    pytest.mark.journey("JOURNEY-DEV-001"),
]


@pytest.mark.integration
@requires_backend
class TestDEVJourney:
    """Developer persona — end-to-end CLI journey."""

    def test_cli_is_installed(self):
        """Verify datahub CLI is callable."""
        result = subprocess.run(
            [*DATAHUB_CLI_CMD, "--help"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0

    def test_capabilities_list(self):
        """CLI ``capabilities list`` returns valid response."""
        data = _cli("capabilities", "list")
        assert data is not None

    def test_developer_portal(self):
        """CLI ``developer portal`` returns valid response.

        The command does not accept ``--format``; the shared helper
        retries without it when the option is unrecognised.
        """
        data = _cli("developer", "portal")
        assert data is not None
