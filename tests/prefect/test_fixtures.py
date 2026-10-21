"""Smoke tests for Prefect test fixtures.

Validates that Prefect Server fixtures are importable, return expected
types, and degrade gracefully when the server is unavailable.
"""

from __future__ import annotations


class TestPrefectFixtures:
    """Prefect test fixtures are correctly wired."""

    def test_prefect_server_url_returns_string(self, prefect_server_url):
        """Fixture returns a non-empty string."""
        assert isinstance(prefect_server_url, str)
        assert len(prefect_server_url) > 0

    def test_prefect_server_health_is_bool(self, prefect_server_health):
        """Health check returns a boolean (may be False if server absent)."""
        assert isinstance(prefect_server_health, bool)

    def test_prefect_server_available_succeeds_or_skips(self, prefect_server_available):
        """Either the server is available and the fixture returns True,
        or it was skipped — we never reach here with False."""
        assert prefect_server_available is True
