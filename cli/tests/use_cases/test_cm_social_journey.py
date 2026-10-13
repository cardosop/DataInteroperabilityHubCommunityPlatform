"""
Phase 279.H.cm_social — Community Manager persona journey tests (CLI).

Tests the Community Manager end-to-end workflow through the CLI.

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
    pytest.mark.journey("JOURNEY-CM-001"),
]


@pytest.mark.integration
@requires_backend
class TestCMJourney:
    """Community Manager persona — end-to-end CLI journey."""

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

    def test_users_list(self):
        """CLI ``users list`` returns valid response."""
        data = _cli("users", "list")
        assert data is not None

    def test_assets_list(self):
        """CLI ``assets list`` returns valid response."""
        data = _cli("assets", "list")
        assert data is not None
