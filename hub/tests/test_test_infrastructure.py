"""
112.E — Test infrastructure honesty tests.

Proves:
1. E.1: hub/conftest.py imports tests/conftest.py (single-source bridging)
2. E.2: STRICT_TEST_TEARDOWN flag controls teardown error suppression
3. E.2: Teardown resilience covers statement-timeout errors
4. E.3: Production DB guard blocks prod-like names and hosts
"""

import os
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class ConftestConsolidationTest(TestCase):
    """E.1 — Verify conftest bridging works."""

    def test_hub_conftest_imports_tests_conftest(self):
        """
        hub/conftest.py must import tests.conftest so patches
        are applied even for hub-only test runs.
        """
        import hub.conftest as hub_conf

        source = open(hub_conf.__file__).read()
        self.assertIn(
            "import tests.conftest",
            source,
            "hub/conftest.py must import tests/conftest.py for single-source patch bridging",
        )

    def test_hub_conftest_delegates_pytest_configure(self):
        """
        hub/conftest.py's pytest_configure must call
        tests.conftest.pytest_configure when available.
        """
        import hub.conftest as hub_conf

        source = open(hub_conf.__file__).read()
        self.assertIn(
            "tests_conftest.pytest_configure(config)",
            source,
            "hub/conftest.py must delegate to tests.conftest.pytest_configure",
        )

    def test_sql_flush_cascade_patch_idempotent(self):
        """
        The sql_flush CASCADE patch must have idempotency
        guard (_patched_for_cascade) so it's never
        double-applied.
        """
        import django.db.backends.postgresql.operations as pg_ops

        self.assertTrue(
            getattr(
                pg_ops.DatabaseOperations.sql_flush,
                "_patched_for_cascade",
                False,
            ),
            "sql_flush must have _patched_for_cascade sentinel",
        )


class StrictTeardownFlagTest(TestCase):
    """E.2 — Verify STRICT_TEST_TEARDOWN behaviour."""

    def test_teardown_resilience_covers_statement_timeout(self):
        """
        The teardown resilience handler in hub/conftest.py must
        suppress 'canceling statement' / 'statement timeout'
        errors (PgBouncer statement_timeout during TRUNCATE).
        """
        import hub.conftest as hub_conf

        source = open(hub_conf.__file__).read()
        self.assertIn(
            '"canceling statement"',
            source,
            "Teardown must handle 'canceling statement' (PgBouncer statement_timeout)",
        )
        self.assertIn(
            '"statement timeout"',
            source,
            "Teardown must handle 'statement timeout'",
        )

    def test_strict_flag_documented_in_conftest(self):
        """
        STRICT_TEST_TEARDOWN must be documented in the
        hub/conftest.py module docstring.
        """
        import hub.conftest as hub_conf

        self.assertIn(
            "STRICT_TEST_TEARDOWN",
            hub_conf.__doc__,
            "STRICT_TEST_TEARDOWN must be documented in hub/conftest.py docstring",
        )

    def test_strict_flag_checked_in_teardown(self):
        """
        All three teardown error handlers must check
        STRICT_TEST_TEARDOWN and raise if set.
        """
        import hub.conftest as hub_conf

        source = open(hub_conf.__file__).read()
        # Count occurrences of STRICT_TEST_TEARDOWN check
        count = source.count('os.environ.get("STRICT_TEST_TEARDOWN") == "1"')
        self.assertGreaterEqual(
            count,
            3,
            "STRICT_TEST_TEARDOWN must be checked in all "
            "three teardown error handlers (Operational, "
            "Programming, Integrity)",
        )


@pytest.mark.filterwarnings("ignore::UserWarning")
@patch.dict(os.environ, {"SKIP_PROD_DB_GUARD": ""}, clear=False)
class ProductionDBGuardTest(TestCase):
    """E.3 — Verify production DB guard blocks unsafe names.

    Uses @patch.dict to ensure SKIP_PROD_DB_GUARD is never set
    during these tests — otherwise the guard returns early and the
    'blocks' assertions fail.
    """

    def test_guard_blocks_prod_in_db_name(self):
        """DB name containing 'prod' must be rejected."""
        from hub.test_runner import _guard_against_production_db

        with self.settings(
            DATABASES={"default": {"NAME": "meshant_prod", "HOST": "localhost"}},
        ):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                _guard_against_production_db()
            self.assertIn("prod", str(ctx.exception).lower())

    def test_guard_blocks_production_in_db_name(self):
        """DB name containing 'production' must be rejected."""
        from hub.test_runner import _guard_against_production_db

        with (
            self.settings(
                DATABASES={"default": {"NAME": "hub_production", "HOST": "localhost"}},
            ),
            self.assertRaises(ImproperlyConfigured),
        ):
            _guard_against_production_db()

    def test_guard_blocks_live_in_db_name(self):
        """DB name containing 'live' must be rejected."""
        from hub.test_runner import _guard_against_production_db

        with (
            self.settings(
                DATABASES={"default": {"NAME": "hub_live_db", "HOST": "localhost"}},
            ),
            self.assertRaises(ImproperlyConfigured),
        ):
            _guard_against_production_db()

    def test_guard_blocks_prod_in_host(self):
        """Host containing 'prod' (without 'test') must be rejected."""
        from hub.test_runner import _guard_against_production_db

        with self.settings(
            DATABASES={"default": {"NAME": "hub_test", "HOST": "db-prod.rds.amazonaws.com"}},
        ):
            with self.assertRaises(ImproperlyConfigured) as ctx:
                _guard_against_production_db()
            self.assertIn("host", str(ctx.exception).lower())

    def test_guard_allows_test_db_name(self):
        """DB name with 'test' must be allowed."""
        from hub.test_runner import _guard_against_production_db

        with self.settings(
            DATABASES={"default": {"NAME": "hub_test_shared", "HOST": "postgres"}},
        ):
            # Must not raise
            _guard_against_production_db()

    def test_guard_allows_prod_test_host(self):
        """Host containing both 'prod' and 'test' must be allowed."""
        from hub.test_runner import _guard_against_production_db

        with self.settings(
            DATABASES={"default": {"NAME": "hub_test", "HOST": "prod-test-db.internal"}},
        ):
            # Must not raise (host has both 'prod' and 'test')
            _guard_against_production_db()

    def test_guard_called_in_test_runner(self):
        """NoMigrateTestRunner.setup_databases must call the guard."""
        import hub.test_runner as runner_mod

        source = open(runner_mod.__file__).read()
        self.assertIn(
            "_guard_against_production_db()",
            source,
            "setup_databases must call _guard_against_production_db",
        )
