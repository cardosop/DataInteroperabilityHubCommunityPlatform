# -*- coding: utf-8 -*-
"""
Pytest conftest for hub app tests.

Applies the sql_flush CASCADE patch so test teardown (flush) works with PostgreSQL
when tables have foreign key constraints (e.g. ingestion_templates -> tenants).
Without this, tests using transaction=True fail with:
  cannot truncate a table referenced in a foreign key constraint

Note: test_create_job and test_create_job_api assert job enqueued to RQ. When the
worker service is running, it may consume the job before the assertion. Run with
REDIS_QUEUE_URL=.../1 (e.g. redis://redis-queue:6379/1) so the test process uses
a different Redis DB and the worker (on db 0) does not consume the job.

Ensures repo root is on sys.path so hub app tests can import tests.utils.polling
(wait_until) for root-cause flaky fixes (no fixed time.sleep).

Sets TESTING=1 so app code (e.g. contract permission checks) can detect test runs
when only hub/apps tests are executed (batch runs); tests/conftest.py sets it for
full-suite runs, but that conftest may not be loaded when testpaths collect only
from hub/apps.
"""

import os
import sys
import time
from pathlib import Path

import pytest

# Allow hub app tests to import tests.utils.polling (wait_until) when run from hub/ or repo root
_repo_root = Path(__file__).resolve().parents[1]
if _repo_root.exists() and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Defaults for DB connectivity check (used only when env not set). Read at runtime in pytest_sessionstart.
_DB_CHECK_RETRIES_DEFAULT = "72"
_DB_CHECK_INTERVAL_DEFAULT = "5.0"


def _get_db_check_retries():
    """Read retry count at runtime so batch script env (docker exec -e) is always used."""
    return int(os.environ.get("DB_CONNECTIVITY_CHECK_RETRIES", _DB_CHECK_RETRIES_DEFAULT))


def _get_db_check_interval():
    """Read interval at runtime so batch script env is always used."""
    return float(os.environ.get("DB_CONNECTIVITY_CHECK_INTERVAL", _DB_CHECK_INTERVAL_DEFAULT))


def pytest_sessionstart(session):
    """Verify DB is reachable at session start so batch fails fast if PostgreSQL is down.

    Uses a direct psycopg2 connection to the 'postgres' database (always exists)
    instead of Django's connection.ensure_connection(), avoiding pytest-django's
    "database access not allowed" at session start and avoiding failure when the
    test DB name is generated (e.g. hub_test_test_4492774a) and not yet created.

    When Postgres is transiently unavailable ("starting up", "not yet accepting
    connections", "consistent recovery state has not been yet reached", "refused"),
    retries with backoff so batch runs started right after docker compose up succeed
    once the database is ready. Retries/interval read at hook runtime from env so
    run_phase_12a_batched.sh -e DB_CONNECTIVITY_CHECK_RETRIES=72 is always honored.
    """
    if os.environ.get("SKIP_DB_CONNECTIVITY_CHECK", "").lower() in ("1", "true", "yes"):
        return
    sys.stderr.write("Checking PostgreSQL connectivity... ")
    sys.stderr.flush()
    db_check_retries = _get_db_check_retries()
    db_check_interval = _get_db_check_interval()
    try:
        import django
        django.setup()
        from django.conf import settings as django_settings

        db = django_settings.DATABASES.get("default", {})
        if "postgresql" not in (db.get("ENGINE") or ""):
            return
        try:
            import psycopg2
        except ImportError:
            return
        host = db.get("HOST") or "localhost"
        port = int(db.get("PORT") or 5432)
        user = db.get("USER") or ""
        password = db.get("PASSWORD") or ""
        last_error = None
        for attempt in range(1, db_check_retries + 1):
            try:
                conn = psycopg2.connect(
                    host=host,
                    port=port,
                    user=user,
                    password=password,
                    dbname="postgres",
                    connect_timeout=5,
                )
                conn.close()
                sys.stderr.write("OK\n")
                sys.stderr.flush()
                return
            except Exception as e:
                last_error = e
                err = str(e).lower()
                # Transient: retry (Postgres starting, shutting down/restarting, in recovery, or Docker DNS not ready)
                if (
                    "starting up" in err
                    or "shutting down" in err
                    or "refused" in err
                    or "not yet accepting connections" in err
                    or "consistent recovery" in err
                    or "recovery state has not been" in err
                    or "could not translate host name" in err
                    or "temporary failure in name resolution" in err
                    or "name or service not known" in err
                ):
                    if attempt < db_check_retries:
                        time.sleep(db_check_interval)
                        continue
                    raise RuntimeError(
                        "PostgreSQL still not ready after %s attempts (e.g. starting up or "
                        "recovery). Ensure the database is running and stable. "
                        "Set SKIP_DB_CONNECTIVITY_CHECK=1 to skip."
                        % db_check_retries
                    ) from e
                # Non-transient or final attempt: decide whether to raise
                if "shutting down" in err or "closed" in err:
                    raise RuntimeError(
                        "PostgreSQL is not reachable at test session start. "
                        "Ensure the database is running and stable "
                        "(e.g. docker compose up -d, pg_isready). "
                        "See docs/TEST_EXECUTION_PLAN.md. "
                        "Set SKIP_DB_CONNECTIVITY_CHECK=1 to skip."
                    ) from e
                if "connection" in err and "does not exist" not in err:
                    if attempt >= db_check_retries:
                        raise RuntimeError(
                            "PostgreSQL is not reachable at test session start after "
                            "%s attempts. Set SKIP_DB_CONNECTIVITY_CHECK=1 to skip."
                            % db_check_retries
                        ) from e
                    time.sleep(db_check_interval)
                    continue
                # Other errors (e.g. "database X does not exist", import, config): no retry
                break
        if last_error is not None:
            err = str(last_error).lower()
            if "shutting down" in err or "refused" in err or "closed" in err:
                raise RuntimeError(
                    "PostgreSQL is not reachable at test session start. "
                    "Ensure the database is running and stable. "
                    "Set SKIP_DB_CONNECTIVITY_CHECK=1 to skip."
                ) from last_error
            if "connection" in err and "does not exist" not in err:
                raise RuntimeError(
                    "PostgreSQL is not reachable at test session start. "
                    "Set SKIP_DB_CONNECTIVITY_CHECK=1 to skip."
                ) from last_error
        # Other errors: continue (e.g. database does not exist, config)
        pass
    except RuntimeError:
        raise
    except Exception:
        # Django setup or config errors: allow session to proceed (e.g. non-Postgres backend)
        pass


def _ensure_db_connection_impl():
    """Ensure default DB connection is open; reconnect only if closed.

    Do not call close_all() here: it would close the connection pytest-django uses
    for the test's transaction and cause 'connection already closed' in setUp.
    """
    try:
        from django.db import connection

        connection.ensure_connection()
    except Exception:
        try:
            from django.db import connections

            connections.close_all()
            connection.ensure_connection()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _ensure_db_connection_before_test():
    """Ensure the default DB connection is open before each test (after fixtures like db are set up)."""
    _ensure_db_connection_impl()
    yield


def pytest_collection_modifyitems(config, items):
    """Skip tests marked real_scheduled_e2e unless REAL_SCHEDULED_E2E=1 (env-gated real E2E)."""
    if not items:
        return
    guard = os.environ.get("REAL_SCHEDULED_E2E", "").strip() == "1"
    skip_real = pytest.mark.skip(
        reason="Real scheduled ingestion/export E2E: set REAL_SCHEDULED_E2E=1 to run (see docs/runbooks/REAL_SCHEDULED_INGESTION_EXPORT_E2E.md)"
    )
    for item in items:
        if not guard and item.get_closest_marker("real_scheduled_e2e"):
            item.add_marker(skip_real)

    # When BATCH_TEST=1, deselect scheduled_ingestion_integration (requires real S3/Prefect).
    # Ensures batch 16 (Jobs) has 0 skips; run with REAL_SCHEDULED_E2E=1 for full integration.
    if os.environ.get("BATCH_TEST") == "1":
        deselected = [i for i in items if i.get_closest_marker("scheduled_ingestion_integration")]
        if deselected:
            remaining = [i for i in items if i not in deselected]
            config.hook.pytest_deselected(items=deselected)
            items[:] = remaining


def pytest_configure(config):
    """Apply patches and env before any hub app tests run."""
    # Ensure app code can detect test environment when only hub/apps tests run
    # (e.g. batch runs that collect only from hub/apps; tests/conftest.py may not load)
    os.environ.setdefault("TESTING", "1")
    try:
        import django.db.backends.postgresql.operations as pg_operations

        if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
            _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

            def _patched_sql_flush(
                self, style, tables, *, reset_sequences=False, allow_cascade=False
            ):
                return _original_sql_flush(
                    self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
                )

            _patched_sql_flush._patched_for_cascade = True
            pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
    except Exception:
        pass

    # When only hub/apps paths are run (e.g. batch 52), tests/conftest.py is not loaded,
    # so setup_databases is never patched with retry. Wrap it here so transient Postgres
    # errors ("server closed the connection unexpectedly" during long migrate) get retried.
    try:
        import django.test.utils

        if not getattr(django.test.utils.setup_databases, "_hub_retry_wrapped", False):
            from django.db.utils import OperationalError

            _original_setup_databases = django.test.utils.setup_databases

            def _setup_databases_with_retry(*args, **kwargs):
                last_exc = None
                msg_lower = ""
                for attempt in range(1, 21):  # up to 20 attempts
                    try:
                        return _original_setup_databases(*args, **kwargs)
                    except OperationalError as e:
                        last_exc = e
                        msg_lower = str(e).lower()
                        transient = (
                            "shutting down" in msg_lower
                            or "connection closed" in msg_lower
                            or "connection refused" in msg_lower
                            or "server closed the connection" in msg_lower
                            or "terminated abnormally" in msg_lower
                            or "could not translate host name" in msg_lower
                            or "temporary failure in name resolution" in msg_lower
                            or "name or service not known" in msg_lower
                            or "recovery" in msg_lower
                            or "starting up" in msg_lower
                            or "consistent recovery" in msg_lower
                        )
                        if not transient:
                            raise
                        # DNS/name resolution: Docker DNS can be slow; use more attempts and longer delay
                        is_dns = (
                            "could not translate host name" in msg_lower
                            or "temporary failure in name resolution" in msg_lower
                            or "name or service not known" in msg_lower
                        )
                        is_recovery = (
                            "recovery" in msg_lower or "starting up" in msg_lower
                        )
                        max_attempts = 15 if (is_dns or is_recovery) else 5
                        if attempt >= max_attempts:
                            raise
                        try:
                            from django.db import connections

                            for conn in connections.all():
                                conn.close()
                        except Exception:
                            pass
                        delay = 10 if (is_dns or is_recovery) else (5 * attempt)
                        time.sleep(delay)
                if last_exc is not None:
                    raise last_exc

            _setup_databases_with_retry._hub_retry_wrapped = True
            django.test.utils.setup_databases = _setup_databases_with_retry
    except Exception:
        pass

    # Make fixture teardown (flush) resilient to Postgres being unavailable during long runs.
    # When Postgres restarts (e.g. container restart, OOM), teardown can hit "shutting down" or
    # "starting up". The test already passed; treat teardown failure as non-fatal: close
    # connections and return so the test is not reported as ERROR.
    # When a batch log shows shutdown, run_phase_12a_batched.sh waits for Postgres then
    # re-runs failed tests with pytest --lf once, so transient infra failures are recovered.
    try:
        from django.test.testcases import TestCase as DjangoTestCase
        from django.db.utils import OperationalError as DjangoOperationalError

        if not getattr(DjangoTestCase._fixture_teardown, "_hub_teardown_resilient", False):
            _original_fixture_teardown = DjangoTestCase._fixture_teardown

            def _fixture_teardown_resilient(self):
                try:
                    _original_fixture_teardown(self)
                except DjangoOperationalError as e:
                    msg = str(e).lower()
                    if "shutting down" in msg or "starting up" in msg or "closed" in msg:
                        try:
                            from django.db import connections
                            for conn in connections.all():
                                conn.close()
                        except Exception:
                            pass
                        return
                    raise

            _fixture_teardown_resilient._hub_teardown_resilient = True
            DjangoTestCase._fixture_teardown = _fixture_teardown_resilient
    except Exception:
        pass
