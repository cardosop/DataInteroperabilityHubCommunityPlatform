"""
Phase 279.H.de_data_pipeline — Data Engineer persona journey tests (CLI).

Tests the Data Engineer end-to-end workflow through the CLI.

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
    pytest.mark.journey("JOURNEY-DE-001"),
]


@pytest.mark.integration
@requires_backend
class TestDEJourney:
    """Data Engineer persona — end-to-end CLI journey."""

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

    def test_datasets_list(self):
        """CLI ``datasets list`` returns valid response."""
        data = _cli("datasets", "list")
        assert data is not None

    def test_contracts_list(self):
        """CLI ``contracts list`` returns valid response."""
        data = _cli("contracts", "list")
        assert data is not None

    def test_assets_list(self):
        """CLI ``assets list`` returns valid response."""
        data = _cli("assets", "list")
        assert data is not None
