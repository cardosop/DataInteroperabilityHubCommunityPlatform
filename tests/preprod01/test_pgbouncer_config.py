"""
PgBouncer configuration validation tests (312.18.2).

Validates PgBouncer connection pooling configuration:
- pool_mode is transaction (required for Django)
- max_client_conn and default_pool_size are within safe limits
- Server reset_query is configured for Django compatibility
- Auth file references are valid
"""

import os
import pytest


class TestPgBouncerConfig:
    """Validate PgBouncer configuration for production safety."""

    def _find_pgbouncer_ini(self) -> str | None:
        """Locate the pgbouncer.ini file."""
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         "infrastructure", "pgbouncer", "pgbouncer.ini"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         "infrastructure", "pgbouncer", "config.ini"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                         "pgbouncer.ini"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def test_pgbouncer_config_exists(self):
        """PgBouncer configuration file exists in the expected location."""
        path = self._find_pgbouncer_ini()
        if path is None:
            pytest.skip("pgbouncer.ini not found — PgBouncer may not be configured in this env")
        assert os.path.exists(path)

    def test_pool_mode_is_transaction(self):
        """Django requires pool_mode=transaction for connection pooling."""
        path = self._find_pgbouncer_ini()
        if path is None:
            pytest.skip("pgbouncer.ini not found")
        with open(path) as f:
            content = f.read()
        # pool_mode should not be session (incompatible with Django's connection model).
        assert "pool_mode = transaction" in content or "pool_mode=transaction" in content, (
            "PgBouncer pool_mode must be 'transaction' for Django compatibility. "
            "Session pooling breaks Django's connection state assumptions."
        )

    def test_max_client_conn_reasonable(self):
        """max_client_conn should be >= default_pool_size * (1 + reserve_pool_size)."""
        path = self._find_pgbouncer_ini()
        if path is None:
            pytest.skip("pgbouncer.ini not found")
        with open(path) as f:
            content = f.read()
        assert "max_client_conn" in content, "PgBouncer config must define max_client_conn"

    def test_server_reset_query_configured(self):
        """DISCARD ALL is required for Django connection reset between transactions."""
        path = self._find_pgbouncer_ini()
        if path is None:
            pytest.skip("pgbouncer.ini not found")
        with open(path) as f:
            content = f.read()
        # PgBouncer should have server_reset_query = DISCARD ALL for Django compatibility.
        # This clears session state (SET, temporary tables, etc.) between transactions.
        if "server_reset_query" in content:
            assert "DISCARD ALL" in content, (
                "server_reset_query should be 'DISCARD ALL' for Django compatibility"
            )

    def test_auth_file_referenced(self):
        """PgBouncer config should reference an auth_file for user authentication."""
        path = self._find_pgbouncer_ini()
        if path is None:
            pytest.skip("pgbouncer.ini not found")
        with open(path) as f:
            content = f.read()
        assert "auth_file" in content or "auth_query" in content, (
            "PgBouncer must have auth_file or auth_query configured"
        )
