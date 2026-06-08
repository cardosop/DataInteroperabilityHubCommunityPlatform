"""
Custom test runner that can skip migrations when reusing an existing test DB.

When SKIP_TEST_MIGRATIONS=1 (and --keepdb), the test runner does not run
migrate at all: it reuses the existing test database as-is. Use this when
the test DB is already fully migrated (e.g. from a previous run or from
another test suite like phase 6.6).
"""

import os
import time

from django.db.backends.postgresql.creation import DatabaseCreation as PostgresDatabaseCreation
from django.db.transaction import TransactionManagementError
from django.test.runner import DiscoverRunner


def _skip_migrations():
    return os.environ.get("SKIP_TEST_MIGRATIONS", "").strip().lower() in ("1", "true", "yes")


def _ensure_connection_with_retry(connection, max_attempts=3, delay=5):
    """Ensure DB connection with retries for transient timeouts (e.g. Docker postgres under load)."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            connection.ensure_connection()
            return
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                time.sleep(delay)  # INTENTIONAL: test-specific timing requirement
            else:
                raise last_error


class NoMigrateDatabaseCreation(PostgresDatabaseCreation):
    """PostgreSQL DatabaseCreation that skips the migrate call when SKIP_TEST_MIGRATIONS=1."""

    def create_test_db(self, verbosity=1, autoclobber=False, serialize=None, keepdb=False):
        if not _skip_migrations():
            return super().create_test_db(
                verbosity=verbosity,
                autoclobber=autoclobber,
                serialize=serialize,
                keepdb=keepdb,
            )
        # Reuse existing DB: create DB if needed, then skip migrate entirely
        from django.conf import settings
        from django.core.management import call_command

        test_database_name = self._get_test_db_name()
        if verbosity >= 1:
            self.log(
                "Using existing test database for alias %s (SKIP_TEST_MIGRATIONS=1, no migrate)..."
                % (self._get_database_display_str(verbosity, test_database_name),)
            )
        self._create_test_db(verbosity, autoclobber, keepdb)
        self.connection.close()
        settings.DATABASES[self.connection.alias]["NAME"] = test_database_name
        self.connection.settings_dict["NAME"] = test_database_name
        call_command("createcachetable", database=self.connection.alias)
        _ensure_connection_with_retry(self.connection)
        return test_database_name


def _guard_against_production_db():
    """Raise if the configured database name or host looks like production.

    Checks both NAME and HOST against common production indicators.
    Set SKIP_PROD_DB_GUARD=1 to bypass (not recommended).
    """
    import os
    if os.environ.get("SKIP_PROD_DB_GUARD", "").strip().lower() in ("1", "true"):
        return

    from django.conf import settings
    from django.core.exceptions import ImproperlyConfigured

    db = settings.DATABASES.get("default", {})
    db_name = (db.get("NAME") or "").lower()
    db_host = (db.get("HOST") or "").lower()

    # Blocklist tokens for database name
    _BLOCKED_NAME_TOKENS = ("prod", "production", "live")
    for token in _BLOCKED_NAME_TOKENS:
        if token in db_name:
            raise ImproperlyConfigured(
                f"Database name '{db.get('NAME')}' contains '{token}' "
                f"— refusing to run tests against a production database. "
                f"Use a test-specific database. Set SKIP_PROD_DB_GUARD=1 to bypass."
            )

    # Blocklist tokens for host (catch RDS/Cloud SQL production endpoints)
    _BLOCKED_HOST_TOKENS = ("prod", "production", "live")
    for token in _BLOCKED_HOST_TOKENS:
        if token in db_host and "test" not in db_host:
            raise ImproperlyConfigured(
                f"Database host '{db.get('HOST')}' contains '{token}' "
                f"— refusing to run tests against a production host. "
                f"Use a test-specific database. Set SKIP_PROD_DB_GUARD=1 to bypass."
            )


class NoMigrateTestRunner(DiscoverRunner):
    """Test runner that uses NoMigrateDatabaseCreation when SKIP_TEST_MIGRATIONS=1."""

    def _recover_db_connections(self):
        """Ensure all DB connections are alive and in a clean state.

        When a test's setUp errors (e.g. model-kwarg mismatch), Django's
        TestCase rolls back the savepoint but may leave the underlying
        psycopg2 connection in a broken state (closed, aborted transaction,
        InFailedSqlTransaction, or stale needs_rollback flag).

        This method resets every connection so the next test starts with a
        clean state.  It mirrors the three-mode recovery in
        hub/conftest.py's pytest_runtest_setup, which is only active for
        pytest runs — this brings the same resilience to Django's built-in
        test runner.
        """
        from django.db import connections

        for alias in connections:
            conn = connections[alias]
            try:
                if conn.connection is None:
                    continue
                if conn.connection.closed:
                    # Mode 1: connection dead at the psycopg2 level — full reset
                    conn.needs_rollback = False
                    conn.in_atomic_block = False
                    conn.savepoint_ids = []
                    conn.atomic_blocks = []
                    conn.connection = None
                    try:
                        conn.ensure_connection()
                    except Exception:
                        pass
                elif conn.needs_rollback:
                    # Mode 2: transaction aborted — full connection reset.
                    # A simple conn.rollback() breaks Django TestCase's outer
                    # atomic block, so we close and reopen instead.
                    try:
                        conn.needs_rollback = False
                        conn.in_atomic_block = False
                        conn.savepoint_ids = []
                        conn.atomic_blocks = []
                        conn.close()
                        conn.ensure_connection()
                    except Exception:
                        pass
                else:
                    # Mode 3: Django thinks everything is clean but the raw
                    # PostgreSQL connection is in InFailedSqlTransaction.
                    # Verify with SELECT 1; on failure, rollback + reopen.
                    try:
                        raw = conn.connection.cursor()
                        raw.execute("SELECT 1")
                        raw.close()
                    except Exception:
                        conn.needs_rollback = False
                        conn.in_atomic_block = False
                        conn.savepoint_ids = []
                        conn.atomic_blocks = []
                        try:
                            if conn.connection and not conn.connection.closed:
                                conn.connection.rollback()
                        except Exception:
                            pass
                        try:
                            conn.close()
                        except Exception:
                            pass
                        try:
                            conn.ensure_connection()
                        except Exception:
                            pass
            except Exception:
                pass

    def setup_databases(self, **kwargs):
        _guard_against_production_db()  # Phase 95 safeguard

        # Patch Django's TestCase._post_teardown to include connection
        # recovery after every test (mirroring the resilience that
        # hub/conftest.pyʼs pytest_runtest_setup provides for pytest runs).
        self._install_post_teardown_connection_recovery()

        if not _skip_migrations():
            return super().setup_databases(**kwargs)
        # Replace each connection's creation with our no-migrate creation
        from django.db import connections

        for alias in connections:
            conn = connections[alias]
            conn.creation = NoMigrateDatabaseCreation(conn)
        return super().setup_databases(**kwargs)

    def _install_post_teardown_connection_recovery(self):
        """Wrap TestCase._post_teardown so connections are recovered after each test.

        This is a one-time patch applied during test-runner setup.  The
        wrapper calls the original _post_teardown and then runs the
        three-mode connection recovery.

        Also patches ``_remove_databases_failures`` so it tolerates
        connection-method wrappers that have lost their ``.wrapped``
        attribute (e.g. after ``import pytest`` monkey-patches
        Django's internals when running via ``manage.py test``).
        """
        try:
            from django.test import TestCase as DjangoTestCase

            # ── _post_teardown connection recovery ─────────────────
            if not getattr(DjangoTestCase._post_teardown, "_hub_recovery_wrapped", False):
                _original_post_teardown = DjangoTestCase._post_teardown
                _recover = self._recover_db_connections

                def _post_teardown_with_recovery(self):
                    try:
                        _original_post_teardown(self)
                    except TransactionManagementError:
                        # TransactionTestCase._fixture_teardown flushes the
                        # database (TRUNCATE), which commits outside an atomic
                        # block.  When Django's _post_teardown subsequently
                        # calls set_rollback(False), there is no active
                        # transaction to roll back.  The database is already
                        # clean — the error is cosmetic.
                        pass
                    finally:
                        _recover()

                _post_teardown_with_recovery._hub_recovery_wrapped = True
                DjangoTestCase._post_teardown = _post_teardown_with_recovery

            # ── _remove_databases_failures resilience ─────────────
            if not getattr(DjangoTestCase._remove_databases_failures, "_hub_remove_db_failures_patched", False):
                _original_remove = DjangoTestCase._remove_databases_failures

                @classmethod
                def _remove_databases_failures_resilient(cls):
                    from django.db import connections
                    for alias in connections:
                        if alias in cls.databases:
                            continue
                        connection = connections[alias]
                        for name, _ in cls._disallowed_connection_methods:
                            method = getattr(connection, name)
                            # When pytest monkey-patches Django's internals
                            # the _DatabaseFailure wrapper may be replaced
                            # with a plain function that lacks ``.wrapped``.
                            # Default to the method itself in that case.
                            original = getattr(method, "wrapped", method)
                            setattr(connection, name, original)

                _remove_databases_failures_resilient._hub_remove_db_failures_patched = True
                DjangoTestCase._remove_databases_failures = _remove_databases_failures_resilient
        except Exception:
            pass
