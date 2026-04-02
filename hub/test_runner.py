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

    def setup_databases(self, **kwargs):
        _guard_against_production_db()  # Phase 95 safeguard
        if not _skip_migrations():
            return super().setup_databases(**kwargs)
        # Replace each connection's creation with our no-migrate creation before parent runs
        from django.db import connections

        for alias in connections:
            conn = connections[alias]
            conn.creation = NoMigrateDatabaseCreation(conn)
        return super().setup_databases(**kwargs)
