"""Phase 89: Verify PostgreSQL statement_timeout is configured.

Django test OPTIONS set statement_timeout=120s (see hub/settings.py).
hub/conftest.py ``pytest_runtest_setup`` sets the same on each test so
TransactionTestCase teardown's temporary 10s timeout cannot leak across tests.
pytest-timeout (300s in pytest.ini) still bounds hung tests overall.
"""
from django.test import TestCase
from django.db import connection


def _parse_pg_timeout_seconds(raw: str) -> int:
    """Parse a PostgreSQL timeout value (e.g. '55s', '60000ms', '5min') to seconds."""
    if raw.endswith("ms"):
        return int(raw[:-2]) // 1000
    elif raw.endswith("min"):
        return int(raw[:-3]) * 60
    elif raw.endswith("s"):
        return int(raw[:-1])
    raise ValueError(f"Unexpected timeout format: {raw}")


class TestDatabaseTimeout(TestCase):
    """Verify statement_timeout is set at the session level."""

    def test_statement_timeout_configured(self):
        """statement_timeout must match parallel-test policy (120s session)."""
        with connection.cursor() as cursor:
            cursor.execute("SHOW statement_timeout")
            result = cursor.fetchone()[0]
        seconds = _parse_pg_timeout_seconds(result)
        self.assertGreaterEqual(seconds, 90, "statement_timeout too low")
        self.assertLessEqual(seconds, 130, "statement_timeout too high")

    def test_idle_in_transaction_timeout_configured(self):
        """idle_in_transaction_session_timeout must be set to ~5 min."""
        with connection.cursor() as cursor:
            cursor.execute("SHOW idle_in_transaction_session_timeout")
            result = cursor.fetchone()[0]
        seconds = _parse_pg_timeout_seconds(result)
        self.assertGreaterEqual(seconds, 60, "idle_in_transaction_session_timeout too low")
        self.assertLessEqual(seconds, 600, "idle_in_transaction_session_timeout too high")
