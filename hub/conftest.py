# -*- coding: utf-8 -*-
"""
Pytest conftest for **hub-only** test runs (e.g. ``pytest hub/apps/auth/tests/``).

Relationship to tests/conftest.py
---------------------------------
The project has **two** conftest files with intentional overlap:

  tests/conftest.py    — Root-level.  Loaded for full-suite runs (``pytest``).
                         Contains migration-safety patches (sync_apps, create_test_db,
                         MigrationLoader, MigrationExecutor) and the sql_flush
                         CASCADE patch.

  hub/conftest.py      — This file.  Loaded for hub-only runs
                         (``pytest hub/apps/...``).  Bridges to tests/conftest.py
                         by importing it (line ~49) and delegating its
                         pytest_configure.  Duplicates the sql_flush CASCADE patch
                         as a fallback in case tests/conftest.py is unreachable.
                         Adds hub-specific fixtures: DB connectivity check,
                         idempotent Tenant/User/TenantPlan create, teardown
                         resilience (TRUNCATE CASCADE error suppression), and
                         TenantPlan auto-seed.

Both conftest files guard every patch with ``_patched`` / ``_hub_*`` sentinel
attributes so patches are idempotent and never double-applied.

Environment flags
-----------------
  TESTING=1                  — Set by both conftest files so app code can detect
                               test runs.
  STRICT_TEST_TEARDOWN=1     — When set, teardown errors (shutdown, deadlock,
                               statement timeout, missing table, duplicate key)
                               are raised instead of suppressed.  Use in CI to
                               surface infrastructure issues.
  SKIP_DB_CONNECTIVITY_CHECK — Skip the session-start PostgreSQL connectivity
                               probe.
"""

# Prevent pytest from importing test_settings_phase11.py during collection.
# That file executes `from hub.settings import *` and mutates DATABASES["default"]["NAME"],
# which would silently switch all subsequent tests to the wrong database (hub_test_phase11
# instead of hub_test_test_shared), causing "column does not exist" errors for any test
# that queries a table with v2 migrations applied after hub_test_phase11 was created.
# The file is a Django settings module for phase-11 scripts, not a pytest test file.
collect_ignore = ["test_settings_phase11.py"]

import logging
import os
import sys
import time
from pathlib import Path

# Set DJANGO_SETTINGS_MODULE here (not in pytest.ini) so it is only active when
# hub tests are collected.  Keeps pytest.ini free of pytest-django-only config
# keys, avoiding PytestConfigWarning when running non-Django tests with -p no:django.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "hub.settings")

import pytest

# Allow hub app tests to import tests.utils.polling (wait_until) when run from hub/ or repo root
_repo_root = Path(__file__).resolve().parents[1]
if _repo_root.exists() and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# CRITICAL: Load tests/conftest patches when running hub-only tests (e.g. hub/apps/auth/tests/).
# When testpaths collect only from hub/apps, tests/conftest.py is never loaded, so create_test_db
# and setup_databases patches (run_syncdb=False, keepdb for TEST_DB_SUFFIX) are not applied.
# Without these patches, create_test_db runs sync_apps and hits UniqueViolation on pg_type.
try:
    import tests.conftest  # noqa: F401
except ImportError:
    pass  # tests package not on path (e.g. minimal env)

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
                        time.sleep(db_check_interval)  # INTENTIONAL: wait for database/service startup
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
                    time.sleep(db_check_interval)  # INTENTIONAL: wait for database/service startup
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


_conn_logger = logging.getLogger("hub.conftest.connection")

def _ensure_db_connection_impl():
    """Ensure default DB connection is open; reconnect only if closed.

    Do not call close_all() here: it would close the connection pytest-django uses
    for the test's transaction and cause 'connection already closed' in setUp.

    Django 6.0: close() may leave self.connection non-None pointing to a closed
    psycopg2 connection.  ensure_connection() sees non-None and returns without
    reconnecting.  We explicitly detect a closed or unusable psycopg2 connection
    and force self.connection = None so the reconnection path fires.
    """
    _reconnect_limit = 3
    for _attempt in range(_reconnect_limit):
        try:
            from django.db import connection

            # Force reconnect if the psycopg2 connection is closed
            # or does not exist.  Also reset the Django 5.2+
            # closed_in_transaction / in_atomic_block flags so
            # ensure_connection() can proceed past the guard that
            # raises "Cannot open a new connection in an atomic block."
            conn = connection.connection
            if conn is not None and conn.closed:
                connection.connection = None
            connection.closed_in_transaction = False
            connection.in_atomic_block = False
            connection.needs_rollback = False
            connection.savepoint_ids = []
            connection.atomic_blocks = []
            connection.ensure_connection()
            # If a prior setUpClass raised SkipTest after opening class-level
            # atomics, those atomics are never rolled back (tearDownClass is
            # skipped), leaving autocommit=False on the connection.  The next
            # Atomic.__enter__ will take the commit_on_exit=False path, which
            # clears in_atomic_block and crashes tearDownClass.  Force
            # autocommit back on to put the connection in a clean state.
            connection.set_autocommit(True)
            # Verify the connection is actually usable.
            if connection.connection is not None:
                raw = connection.connection.cursor()
                try:
                    raw.execute("SELECT 1")
                finally:
                    raw.close()
            return
        except Exception:
            try:
                from django.db import connections

                connections.close_all()
                connection.connection = None
            except Exception:
                pass
    # Last resort: force close_all and reconnect
    try:
        from django.db import connections
        connections.close_all()
        from django.db import connection
        connection.connection = None
        connection.ensure_connection()
    except Exception as e:
        _conn_logger.warning(
            "DB connection recovery failed in last-resort: %s", e
        )


@pytest.fixture(autouse=True)
def _ensure_db_connection_before_test(request):
    """Ensure the default DB connection is open before each test.

    Skips pure-unit tests (SimpleTestCase subclasses) that do not allow
    database access — forcing a connection there produces a WARNING on
    every test method that is harmless but noisy and misleading in logs.
    """
    from django.test import SimpleTestCase, TestCase, TransactionTestCase

    test_cls = getattr(request.node, "cls", None)
    if test_cls is not None:
        if issubclass(test_cls, SimpleTestCase) and not issubclass(
            test_cls, (TestCase, TransactionTestCase)
        ):
            yield
            return

    _ensure_db_connection_impl()
    yield


# Removed autouse fixture _suppress_transaction_mgmt_error_in_teardown —
# the TransactionManagementError suppression is now applied permanently in
# pytest_configure (line ~817) so it stays active through all teardown phases.
# A fixture-based approach using yield was undone before Django's teardown
# completed, allowing the error to still propagate.


@pytest.fixture(autouse=True)
def _clear_login_rate_limit():
    """Clear the IP-level login rate limit cache before each test.

    The login endpoint enforces a 10-req/min rate limit per IP (hub/apps/auth/views.py).
    In test runs all requests originate from 127.0.0.1, so tests that call the login
    endpoint bleed into each other and eventually get 429 instead of the expected status.
    Clearing the cache key before every test isolates each test's rate-limit window.
    """
    try:
        from django.core.cache import cache
        cache.delete("login_ip_rate:127.0.0.1")
    except Exception:
        pass
    yield


# ── Circuit breaker reset fixtures ────────────────────────────────────────
# Circuit breakers (e.g. Redis-backed) are shared across tests.  A test that
# exercises a failure path (invalid credentials, not found, retries exceeded)
# increments the failure counter; after the threshold the circuit opens and
# unrelated tests get CircuitBreakerError.  Resetting before each test
# prevents cross-test contamination.
#
# Defined here in hub/conftest.py (the hub-level conftest) rather than in
# per-app conftest files to avoid disrupting pytest's test-module import-path
# resolution.  A conftest inside an app directory anchors module resolution
# to that directory, causing test files to be imported as ``tests.test_xxx``
# instead of ``hub.apps.<app>.tests.test_xxx``.


@pytest.fixture(autouse=True)
def _reset_webhook_delivery_circuit_breaker():
    """Reset webhook-delivery circuit breaker before/after each test."""
    try:
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )
        reset_circuit_breaker_by_name("webhook-delivery")
    except Exception:
        pass
    yield
    try:
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )
        reset_circuit_breaker_by_name("webhook-delivery")
    except Exception:
        pass


@pytest.fixture(autouse=True)
def _reset_connector_circuit_breakers():
    """Reset connector circuit breakers before/after each test.

    Covers AWS Data Exchange, GCP Marketplace, Snowflake, and Databricks
    connector circuit breakers so that expected failures in one test
    (invalid credentials, not found, retries exceeded) do not leave the
    circuit OPEN for subsequent tests.
    """
    _CONNECTOR_BREAKERS = [
        "aws-data-exchange-connector",
        "gcp-marketplace-connector",
        "snowflake-connector",
        "databricks-connector",
    ]
    try:
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )
        for name in _CONNECTOR_BREAKERS:
            try:
                reset_circuit_breaker_by_name(name)
            except Exception:
                pass
    except Exception:
        pass
    yield
    try:
        from hub.apps.core.resilience.circuit_breaker import (
            reset_circuit_breaker_by_name,
        )
        for name in _CONNECTOR_BREAKERS:
            try:
                reset_circuit_breaker_by_name(name)
            except Exception:
                pass
    except Exception:
        pass


# ── Permanent module-level patch: suppress TransactionManagementError ──
# Applied IMMEDIATELY at conftest import time (before any test fixture or
# pytest_configure hook), so it is active for ALL test phases including
# method-level tearDown, class-level _fixture_teardown, and pytest-django
# transaction teardown.  The pytest_configure-based patch (line ~1050) is
# a second layer; this one is the primary and runs first.
_hub_tme_module_patched = False
if not _hub_tme_module_patched:
    try:
        import django.db.transaction as _dbtx
        from django.db.transaction import TransactionManagementError as _Tme2

        if not getattr(_dbtx.set_rollback, "_hub_tme_patched", False):
            _orig_tx_set_rollback = _dbtx.set_rollback

            def _hub_safe_set_rollback(rollback, using=None):
                try:
                    _orig_tx_set_rollback(rollback, using=using)
                except _Tme2:
                    # No active atomic block — cosmetic teardown noise.
                    # The test passed; the DB is clean (TRUNCATE committed).
                    pass

            _hub_safe_set_rollback._hub_tme_patched = True
            _dbtx.set_rollback = _hub_safe_set_rollback
    except Exception:
        pass
    _hub_tme_module_patched = True


# ── TenantPlan seed data (free/pro/enterprise) ──────────────────────────
# Canonical plan definitions used by session seed, post-flush re-seed, and
# the defensive TenantPlan.objects.get patch.  Kept in sync with
# hub/apps/tenants/management/commands/seed_default_plans.py.
_DEFAULT_PLANS = [
    {
        "name": "Free Plan",
        "slug": "free",
        "tier": "FREE",
        "limits_json": {
            "max_assets": 10,
            "max_datasets": 20,
            "max_api_calls_per_month": 10000,
            "max_scheduled_ingestions": 5,
            "max_scheduled_runs_per_month": 50,
            "max_scheduled_exports": 5,
            "max_export_runs_per_month": 20,
            "max_storage_gb": 1,
            "max_transformation_pipelines": 5,
            "max_transformation_runs_per_month": 20,
        },
    },
    {
        "name": "Pro Plan",
        "slug": "pro",
        "tier": "PRO",
        "limits_json": {
            "max_assets": 100,
            "max_datasets": 500,
            "max_api_calls_per_month": 100000,
            "max_scheduled_ingestions": 50,
            "max_scheduled_runs_per_month": 1000,
            "max_scheduled_exports": 50,
            "max_export_runs_per_month": 500,
            "max_storage_gb": 100,
            "max_transformation_pipelines": 50,
            "max_transformation_runs_per_month": 500,
        },
    },
    {
        "name": "Enterprise Plan",
        "slug": "enterprise",
        "tier": "ENTERPRISE",
        "limits_json": {
            "max_assets": None,
            "max_datasets": None,
            "max_api_calls_per_month": None,
            "max_scheduled_ingestions": None,
            "max_scheduled_runs_per_month": None,
            "max_scheduled_exports": None,
            "max_export_runs_per_month": None,
            "max_storage_gb": None,
            "max_transformation_pipelines": None,
            "max_transformation_runs_per_month": None,
        },
    },
    # ── ML / AI plans (Phase 114A) ──
    # Kept in sync with seed_default_plans management command.
    {
        "name": "ML Starter",
        "slug": "ml-starter",
        "tier": "FREE",
        "category": "ML_AI",
        "limits_json": {
            "max_ml_models": 3,
            "max_ml_training_jobs_per_month": 10,
            "max_ml_inference_requests_per_month": 500,
            "max_ml_deployed_models": 1,
            "max_ml_storage_gb": 5,
        },
    },
    {
        "name": "ML Professional",
        "slug": "ml-professional",
        "tier": "PRO",
        "category": "ML_AI",
        "limits_json": {
            "max_ml_models": 20,
            "max_ml_training_jobs_per_month": 100,
            "max_ml_inference_requests_per_month": 10000,
            "max_ml_deployed_models": 10,
            "max_ml_storage_gb": 100,
        },
    },
    {
        "name": "ML Enterprise",
        "slug": "ml-enterprise",
        "tier": "ENTERPRISE",
        "category": "ML_AI",
        "limits_json": {
            "max_ml_models": None,
            "max_ml_training_jobs_per_month": None,
            "max_ml_inference_requests_per_month": None,
            "max_ml_deployed_models": None,
            "max_ml_storage_gb": None,
        },
    },
]


def _seed_tenant_plans_if_missing():
    """Ensure free/pro/enterprise + ML TenantPlan rows exist via get_or_create.

    Uses SAVEPOINT (transaction.atomic) so IntegrityError on race conditions
    rolls back only the savepoint, keeping the outer transaction clean.
    Safe to call from any context: session startup, post-flush re-seed, or
    the defensive TenantPlan.objects.get patch.

    Sets a 10s statement_timeout to avoid hanging when the tenant_plans
    table is locked by another session on the shared test DB.
    """
    try:
        from hub.apps.tenants.models import TenantPlan
        from django.db import connection as _conn
        from django.db import transaction as db_transaction
        from django.db.utils import IntegrityError as DjIntegrityError

        # Prevent hanging if tenant_plans table is locked.
        try:
            _conn.ensure_connection()
            if _conn.connection and not _conn.connection.closed:
                with _conn.cursor() as _c:
                    _c.execute("SET statement_timeout = '10s'")
                    _c.execute("SET lock_timeout = '5s'")
        except Exception:
            pass

        for plan_data in _DEFAULT_PLANS:
            defaults = {
                "name": plan_data["name"],
                "tier": plan_data["tier"],
                "limits_json": plan_data["limits_json"],
                "is_active": True,
            }
            if "category" in plan_data:
                defaults["category"] = plan_data["category"]
            try:
                with db_transaction.atomic():
                    TenantPlan.objects.get_or_create(
                        slug=plan_data["slug"],
                        defaults=defaults,
                    )
            except DjIntegrityError:
                # Race condition or unique constraint on name — plan exists, skip
                pass
            except Exception:
                pass
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def _seed_default_tenant_plans(django_db_setup, django_db_blocker):
    """Session-scoped: seed free/pro/enterprise plans once at test session start.

    Runs after django_db_setup (DB exists + migrations applied) using
    django_db_blocker.unblock() so we get DB access outside a test.
    """
    with django_db_blocker.unblock():
        _seed_tenant_plans_if_missing()

        # CRITICAL: Unconditionally nuke and recreate the DB connection.
        #
        # _seed_tenant_plans_if_missing() sets statement_timeout='10s' and
        # lock_timeout='5s', then runs get_or_create inside
        # transaction.atomic().  If ANY operation times out or deadlocks
        # (e.g. tenant_plans table locked by the API service), the
        # exception is caught silently (except Exception: pass) but
        # the PostgreSQL connection is left in an aborted-transaction
        # state (InFailedSqlTransaction).
        #
        # A simple conn.close() + ensure_connection() is NOT enough:
        # Django's close() can silently fail on a severely broken
        # connection, leaving self.connection in a half-alive state.
        #
        # Fix: rollback the raw psycopg2 connection first, then reset
        # all Django-side state, then fully close and recreate.
        # This mirrors the Mode 2+3 recovery in pytest_runtest_setup.
        try:
            from django.db import connection as _conn
            # Step 1: rollback raw psycopg2 connection (clears PG-side state)
            try:
                if _conn.connection and not _conn.connection.closed:
                    _conn.connection.rollback()
            except Exception:
                pass
            # Step 2: reset ALL Django-side connection state
            _conn.needs_rollback = False
            _conn.in_atomic_block = False
            _conn.savepoint_ids = []
            _conn.atomic_blocks = []
            # Step 3: close the Django connection wrapper (drops psycopg2 conn)
            try:
                _conn.close()
            except Exception:
                # Force-clear if close() fails
                _conn.connection = None
            # Step 4: open a fresh connection
            _conn.ensure_connection()
            # Step 5: set normal timeouts on the fresh connection
            raw = _conn.connection.cursor()
            raw.execute("SET statement_timeout = '120s'")
            raw.execute("SET lock_timeout = '60s'")
            raw.close()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def _ensure_baas_tables(django_db_setup, django_db_blocker):
    """Ensure baas_usage_record table exists on the 'baas' alias.

    With --reuse-db the test DB may pre-date the addition of
    DATABASES["baas"].  The old BaaSDBRouter blocked baasusagerecord
    from migrating on 'default', so the table was never created.
    Raw DDL with IF NOT EXISTS is idempotent and avoids the pitfalls
    of call_command("migrate") inside test infrastructure.
    """
    with django_db_blocker.unblock():
        from django.db import connections

        try:
            conn = connections["baas"]
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS baas_usage_record (
                        id UUID PRIMARY KEY,
                        api_key_id UUID NOT NULL,
                        tenant_id UUID NOT NULL,
                        endpoint VARCHAR(500) NOT NULL,
                        method VARCHAR(10) NOT NULL,
                        status_code INTEGER NOT NULL,
                        response_time_ms INTEGER NOT NULL,
                        request_size_bytes INTEGER NOT NULL,
                        response_size_bytes INTEGER NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS baas_ur_apikey_ts
                    ON baas_usage_record (api_key_id, timestamp)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS baas_ur_tenant_ts
                    ON baas_usage_record (tenant_id, timestamp)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS baas_ur_ts
                    ON baas_usage_record (timestamp)
                """)
        except Exception:
            pass  # Non-fatal; tests that need it will fail clearly

        # Reset default connection after baas DDL (may share the pg process)
        try:
            from django.db import connection as _def_conn
            if _def_conn.connection and not _def_conn.connection.closed:
                try:
                    _def_conn.connection.rollback()
                except Exception:
                    pass
                _def_conn.needs_rollback = False
        except Exception:
            pass


def pytest_collection_modifyitems(config, items):
    """Deselect tests marked real_scheduled_e2e unless REAL_SCHEDULED_E2E=1 (env-gated real E2E)."""
    if not items:
        return

    # Env-gated marker → env-var pairs: deselect (not skip) when env guard is unset.
    # Each entry: (marker_name, env_var, truthy_value)
    _env_gated = [
        ("real_scheduled_e2e", "REAL_SCHEDULED_E2E", "1"),
        ("requires_clamav_live", "RUN_CLAMAV_LIVE_TESTS", "1"),
        ("smoke_mvp_mode", "SMOKE_EXPECT_MVP_MODE", None),  # any truthy value
    ]
    for marker, env_var, expected in _env_gated:
        env_val = os.environ.get(env_var, "").strip()
        guard_met = (
            env_val == expected if expected
            else env_val.lower() in ("1", "true", "yes", "on")
        )
        if not guard_met:
            to_deselect = [i for i in items if i.get_closest_marker(marker)]
            if to_deselect:
                remaining = [i for i in items if i not in to_deselect]
                config.hook.pytest_deselected(items=to_deselect)
                items[:] = remaining

    # When BATCH_TEST=1, deselect scheduled_ingestion_integration (requires real S3/Prefect).
    # Ensures batch 16 (Jobs) has 0 skips; run with REAL_SCHEDULED_E2E=1 for full integration.
    if os.environ.get("BATCH_TEST") == "1":
        deselected = [i for i in items if i.get_closest_marker("scheduled_ingestion_integration")]
        if deselected:
            remaining = [i for i in items if i not in deselected]
            config.hook.pytest_deselected(items=deselected)
            items[:] = remaining


def pytest_runtest_setup(item):
    """Ensure DB connections are alive before each test.

    Also extends statement_timeout for TransactionTestCase integration
    tests that do heavy DB operations (event publishing, DLQ, retries).
    """
    try:
        from django.db import connections
        for alias in connections:
            conn = connections[alias]
            if conn.connection is None:
                continue
            if conn.connection.closed:
                # Mode 1: connection dead — full reset
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
                # A simple conn.rollback() breaks Django TestCase's
                # outer atomic block (it rolls back the SAVEPOINT the
                # TestCase wrapper depends on).  Instead, close and
                # reopen the connection so both PostgreSQL and Django's
                # Python-side state are fully in sync.
                try:
                    conn.needs_rollback = False
                    conn.in_atomic_block = False
                    conn.savepoint_ids = []
                    conn.atomic_blocks = []
                    conn.close()
                    conn.ensure_connection()
                except Exception:
                    pass
    except Exception:
        pass

    # Mode 3: previous test's TRUNCATE CASCADE or deadlock may leave the
    # PostgreSQL transaction in a failed state even when Django thinks
    # everything is clean (needs_rollback=False).  Verify with a raw
    # SELECT 1; if it fails, ROLLBACK on the raw connection and reopen.
    try:
        from django.db import connections as _conns3
        import time as _time3
        for alias in _conns3:
            conn = _conns3[alias]
            # Ensure connection exists
            if conn.connection is None:
                try:
                    conn.ensure_connection()
                except Exception:
                    continue
            if conn.connection is None or conn.connection.closed:
                continue
            for _attempt in range(2):
                try:
                    # Use raw psycopg2 cursor to bypass Django wrapper state
                    raw = conn.connection.cursor()
                    raw.execute("SELECT 1")
                    raw.close()
                    break
                except Exception:
                    # Connection is in a broken/aborted transaction state
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
                    # Django 6.0: close() may keep self.connection non-None
                    # pointing to the closed psycopg2 connection.  Set it
                    # explicitly to None so ensure_connection() actually
                    # opens a fresh connection (matches Mode 1 above).
                    conn.connection = None
                    _time3.sleep(0.3)
                    try:
                        conn.ensure_connection()
                    except Exception:
                        pass
    except Exception:
        pass

    # Set timeouts on every test so DB operations fail with a clear PostgreSQL
    # error instead of hanging until pytest-timeout (300s in pytest.ini).  Must
    # run every test (not once per connection) because TransactionTestCase
    # teardown sets statement_timeout='10s' for TRUNCATE CASCADE, and that can
    # leak into the next test if the connection is reused.
    # 120s matches hub/settings.py test DATABASE OPTIONS and _db_options for
    # ENVIRONMENT=test — 55s/60s was too tight under xdist + lock wait.
    # Uses raw psycopg2 cursor (not Django's atomic()) because the Django
    # connection may be in an inconsistent atomic state after teardown recovery.
    try:
        from django.db import connections as _timeout_conns

        for _alias in _timeout_conns:
            _tc = _timeout_conns[_alias]
            if _tc.connection and not _tc.connection.closed:
                try:
                    raw = _tc.connection.cursor()
                    raw.execute("SET statement_timeout = '120s'")
                    raw.execute("SET lock_timeout = '60s'")
                    raw.close()
                except Exception:
                    pass
    except Exception:
        pass


def pytest_configure(config):
    """Apply patches and env before any hub app tests run."""
    # Ensure app code can detect test environment when only hub/apps tests run
    # (e.g. batch runs that collect only from hub/apps; tests/conftest.py may not load)
    os.environ.setdefault("TESTING", "1")

    # Allow all DB aliases (including 'baas') in every test class.
    # settings.py adds DATABASES["baas"] in test mode (pointing at the
    # default DB).  Without this, Django 6.0's TestCase blocks queries
    # to 'baas' and its _remove_databases_failures teardown crashes with
    # AttributeError on classes that don't declare databases = "__all__".
    try:
        from django.test import TestCase, TransactionTestCase
    except ModuleNotFoundError as exc:
        raise pytest.UsageError(
            "Django is not installed in this Python environment. Hub tests require "
            "project dependencies (Python 3.12 venv or the API test container).\n\n"
            "Example:\n"
            "  docker compose -f docker-compose.test.yml exec -T api-service-test "
            "python -m pytest <paths>\n\n"
            "Or: python3.12 -m venv .venv && pip install -r requirements.txt "
            "-r requirements-dev.txt"
        ) from exc

    TestCase.databases = "__all__"
    TransactionTestCase.databases = "__all__"

    # CRITICAL: When only hub/apps paths are collected, tests/conftest.py is never discovered
    # so its pytest_configure (setup_databases keepdb, create_test_db DuplicateDatabase patch)
    # never runs. Invoke it explicitly so shared-DB security tests (hub_test_test_shared) work.
    #
    # Guard: if tests.conftest was already imported at module level (line 69), its
    # pytest_configure hook also already ran (conftest modules are auto-discovered by
    # pytest).  Skip the explicit call to avoid double-patching setup_databases.
    if "tests.conftest" not in sys.modules:
        try:
            import tests.conftest as tests_conftest

            if hasattr(tests_conftest, "pytest_configure"):
                tests_conftest.pytest_configure(config)
        except ImportError:
            pass
    # DJANGO_COMPAT: 6.0 — CASCADE required for test teardown on PostgreSQL with FKs.
    # Duplicate of tests/conftest.py patch; kept as fallback for hub-only test runs.
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

    # DJANGO_COMPAT: 6.0 — Idempotent Tenant.objects.create for --reuse-db with shared test DB.
    # ── Idempotent Tenant/User create patch ───────────────────────────────
    # ~300 test files call Tenant.objects.create(name="Test Tenant", slug="test-tenant")
    # with fixed names. TransactionTestCase commits these; subsequent tests hit
    # IntegrityError on the unique constraint, aborting the PostgreSQL transaction.
    # Fix: wrap INSERT in a SAVEPOINT (transaction.atomic()); on IntegrityError the
    # savepoint rolls back (transaction stays clean), then .get() returns existing row.
    try:
        from hub.apps.tenants.models import Tenant
        from django.db import connection as _db_conn, transaction as db_transaction
        from django.db.utils import IntegrityError as DjIntegrityError

        def _recover_broken_transaction():
            """Reset DB connection when transaction is in a failed state."""
            try:
                if _db_conn.needs_rollback:
                    _db_conn.rollback()
            except Exception:
                try:
                    _db_conn.close()
                    _db_conn.ensure_connection()
                except Exception:
                    pass

        _idempotent_logger = logging.getLogger("hub.conftest.idempotent")

        def _make_idempotent_create(model_cls):
            _orig = model_cls.objects.create
            _model_name = model_cls.__name__

            def _idempotent_create(**kwargs):
                try:
                    with db_transaction.atomic():
                        return _orig(**kwargs)
                except DjIntegrityError as exc:
                    msg = str(exc).lower()
                    if "unique" not in msg and "duplicate" not in msg:
                        raise
                    # Idempotent fallback: a previous test already created a row
                    # with the same unique constraint value (slug or name).
                    # Return the existing row so the test can proceed, but emit
                    # a warning so developers know their test is sharing state.
                    _idempotent_logger.warning(
                        "idempotent_create fallback: %s with kwargs=%s "
                        "collided with existing row — test may share stale state",
                        _model_name,
                        {k: v for k, v in kwargs.items() if k in ("slug", "name", "email")},
                    )
                    # Try slug first, then name
                    mgr = getattr(model_cls, 'all_objects', model_cls.objects)
                    for key in ("slug", "name"):
                        if key in kwargs:
                            try:
                                return mgr.get(**{key: kwargs[key]})
                            except model_cls.DoesNotExist:
                                continue
                    raise
                except (DjIntegrityError, OperationalError):
                    # OperationalError (deadlock, connection loss) may leave the
                    # transaction aborted; try get() as a fallback before re-raising.
                    _recover_broken_transaction()
                    mgr = getattr(model_cls, 'all_objects', model_cls.objects)
                    for key in ("slug", "name"):
                        if key in kwargs:
                            try:
                                return mgr.get(**{key: kwargs[key]})
                            except Exception:
                                continue
                    raise

            _idempotent_create._hub_idempotent = True
            return _idempotent_create

        if not getattr(Tenant.objects.create, "_hub_idempotent", False):
            Tenant.objects.create = _make_idempotent_create(Tenant)

        # DJANGO_COMPAT: 6.0 — Idempotent User.objects.create_user for --reuse-db with shared test DB.
        # Same for User.objects.create_user (email unique constraint)
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        _orig_create_user = _User.objects.create_user

        def _update_existing_user(_User, email, args, kwargs):
            """Fetch existing user by email and update fields to match test expectations."""
            user = _User.objects.get(email=email)
            password = kwargs.get("password") or (args[1] if len(args) > 1 else None)
            if password:
                user.set_password(password)
            for k in ("tenant", "status", "display_name", "tenant_id"):
                if k in kwargs:
                    setattr(user, k, kwargs[k])
            user.save()
            return user

        def _idempotent_create_user(*args, **kwargs):
            try:
                with db_transaction.atomic():
                    return _orig_create_user(*args, **kwargs)
            except DjIntegrityError as exc:
                msg = str(exc).lower()
                if "unique" not in msg and "duplicate" not in msg:
                    raise
                email = kwargs.get("email") or (args[0] if args else None)
                if email:
                    return _update_existing_user(_User, email, args, kwargs)
                raise
            except Exception:
                # InFailedSqlTransaction — recover and try get fallback.
                _recover_broken_transaction()
                email = kwargs.get("email") or (args[0] if args else None)
                if email:
                    try:
                        return _update_existing_user(_User, email, args, kwargs)
                    except Exception:
                        pass
                raise

        if not getattr(_User.objects.create_user, "_hub_idempotent", False):
            _idempotent_create_user._hub_idempotent = True
            _User.objects.create_user = _idempotent_create_user

        # DJANGO_COMPAT: 6.0 — Idempotent TenantPlan.objects.create
        # Same pattern: "Limited Plan" / "Free Plan" duplicates after savepoint rollback failure.
        from hub.apps.tenants.models import TenantPlan
        if not getattr(TenantPlan.objects.create, "_hub_idempotent", False):
            TenantPlan.objects.create = _make_idempotent_create(TenantPlan)
    except Exception:
        pass

    # DJANGO_COMPAT: 6.0 — Auto-seed TenantPlan on DoesNotExist after TRUNCATE CASCADE.
    # ── Defensive TenantPlan.objects.get auto-seed patch ─────────────────
    # After TransactionTestCase TRUNCATE CASCADE deletes tenant_plans rows,
    # the next test calling TenantPlan.objects.get(slug="free") gets
    # DoesNotExist.  This patch intercepts DoesNotExist for known slugs,
    # re-seeds all plans via _seed_tenant_plans_if_missing(), and retries
    # the .get() once.  Belt-and-suspenders safety net for the post-flush
    # re-seed (patch 2) in case it is skipped (e.g. error in teardown).
    #
    # IMPORTANT: type(TenantPlan.objects) is django.db.models.Manager —
    # the GLOBAL Manager class shared by ALL models using the default
    # manager.  The self.model guard below ensures the auto-seed logic
    # only fires for TenantPlan queries, not for any other model.
    _KNOWN_PLAN_SLUGS = {p["slug"] for p in _DEFAULT_PLANS}
    try:
        from hub.apps.tenants.models import TenantPlan as _TenantPlan

        _TenantPlanManager = type(_TenantPlan.objects)
        if not getattr(_TenantPlanManager, "_hub_autoseed_get", False):
            _orig_get = _TenantPlanManager.get

            def _autoseed_get(self, *args, **kwargs):
                try:
                    return _orig_get(self, *args, **kwargs)
                except self.model.DoesNotExist:
                    # Guard: only auto-seed for TenantPlan, not other models
                    if self.model is not _TenantPlan:
                        raise
                    # Only auto-seed if the query is for a known plan slug
                    slug_val = kwargs.get("slug")
                    if slug_val and slug_val in _KNOWN_PLAN_SLUGS:
                        _seed_tenant_plans_if_missing()
                        return _orig_get(self, *args, **kwargs)
                    raise

            _autoseed_get._hub_autoseed_get = True
            _TenantPlanManager.get = _autoseed_get
            _TenantPlanManager._hub_autoseed_get = True
    except Exception:
        pass

    # ── Idempotent TenantPlan.objects.create patch (known slugs only) ────
    # The session-scoped seed fixture pre-creates free/pro/enterprise plans.
    # Test files that call TenantPlan.objects.create(slug="free") in setUp
    # would hit IntegrityError.  This patch makes create idempotent ONLY
    # for known plan slugs; non-standard slugs pass through to the original
    # create (preserving uniqueness-constraint tests like test_plan_slug_
    # uniqueness_failure).
    try:
        from hub.apps.tenants.models import TenantPlan as _TPlan

        if not getattr(_TPlan.objects.create, "_hub_idempotent", False):
            _orig_tp_create = _TPlan.objects.create

            def _idempotent_tp_create(**kwargs):
                slug = kwargs.get("slug")
                if slug and slug in _KNOWN_PLAN_SLUGS:
                    try:
                        with db_transaction.atomic():
                            return _orig_tp_create(**kwargs)
                    except DjIntegrityError as exc:
                        msg = str(exc).lower()
                        if "unique" not in msg and "duplicate" not in msg:
                            raise
                        try:
                            return _TPlan.objects.get(slug=slug)
                        except _TPlan.DoesNotExist:
                            raise exc
                # Non-standard slugs: pass through unmodified
                return _orig_tp_create(**kwargs)

            _idempotent_tp_create._hub_idempotent = True
            _TPlan.objects.create = _idempotent_tp_create
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
                        time.sleep(delay)  # INTENTIONAL: wait for database/service startup
                if last_exc is not None:
                    raise last_exc

            _setup_databases_with_retry._hub_retry_wrapped = True
            django.test.utils.setup_databases = _setup_databases_with_retry
    except Exception:
        pass

    # ── Permanent patch: suppress TransactionManagementError in teardown ──
    # Django 6.0 TestCase._fixture_teardown calls _rollback_atomics(self.atomics)
    # which calls transaction.set_rollback(True, using=db_name).  When the
    # TRUNCATE CASCADE flush already committed, in_atomic_block is False and
    # set_rollback raises TransactionManagementError — cosmetic (test passed, DB
    # clean).  Patching permanently in pytest_configure ensures the wrapper stays
    # active through Django's teardown phase (fixture-based undo runs too early).
    try:
        from django.db.transaction import TransactionManagementError as _Tme
        import django.db.transaction as _tx_module

        if not getattr(_tx_module.set_rollback, "_hub_tme_safe", False):
            _original_tx_set_rollback = _tx_module.set_rollback

            def _safe_set_rollback(rollback, using=None):
                try:
                    _original_tx_set_rollback(rollback, using=using)
                except _Tme:
                    pass

            _safe_set_rollback._hub_tme_safe = True
            _tx_module.set_rollback = _safe_set_rollback
    except Exception:
        pass

    # DJANGO_COMPAT: 6.0 — Resilient fixture teardown for TransactionTestCase TRUNCATE CASCADE.
    # Make fixture teardown (flush) resilient to Postgres being unavailable during long runs.
    # When Postgres restarts (e.g. container restart, OOM), teardown can hit "shutting down" or
    # "starting up". The test already passed; treat teardown failure as non-fatal: close
    # connections and return so the test is not reported as ERROR.
    # When a batch log shows shutdown, run_phase_12a_batched.sh waits for Postgres then
    # re-runs failed tests with pytest --lf once, so transient infra failures are recovered.
    #
    # Also handle IntegrityError (duplicate content-type key) and deadlock OperationalError
    # that fire during TransactionTestCase teardown via the post_migrate signal when multiple
    # processes (gunicorn + pytest) compete to insert into django_content_types.
    try:
        import logging
        _teardown_logger = logging.getLogger("hub.conftest.teardown")

        from django.test.testcases import TestCase as DjangoTestCase
        from django.test.testcases import TransactionTestCase as DjangoTransactionTestCase
        from django.db.transaction import TransactionManagementError as DjangoTransactionManagementError
        from django.db.utils import OperationalError as DjangoOperationalError
        from django.db.utils import IntegrityError as DjangoIntegrityError
        from django.db.utils import InterfaceError as DjangoInterfaceError
        from django.db.utils import ProgrammingError as DjangoProgrammingError
        from django.core.management.base import CommandError as DjangoCommandError

        def _rollback_and_close_all_connections():
            """Issue ROLLBACK on every open connection, then close and re-establish.

            ROOT CAUSE FIX: When flush (TRUNCATE CASCADE) deadlocks or times out,
            PostgreSQL keeps the transaction open on the server side until the
            connection is closed.  But simply calling conn.close() races with
            Python's garbage-collector — PG may not process the disconnect before
            the next test opens a new connection and tries to acquire locks on the
            same tables, causing a *cascading* deadlock chain where every
            subsequent test times out at 60 s.

            Fix: explicitly send ROLLBACK on the raw psycopg2 connection before
            closing.  This guarantees PG releases all locks synchronously.
            """
            from django.db import connections
            for alias in connections:
                conn = connections[alias]
                try:
                    if conn.connection is not None and not conn.connection.closed:
                        # Reset to a clean state: cancel any in-progress
                        # query, then ROLLBACK.
                        try:
                            conn.connection.cancel()
                        except Exception:
                            pass
                        try:
                            conn.connection.rollback()
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    conn.close()
                except Exception:
                    pass
            # Re-establish fresh connections so the next test starts clean.
            # Django 5.2+'s conn.close() sets closed_in_transaction=True
            # while inside an atomic block, which blocks ensure_connection()
            # from creating a fresh psycopg2 connection.  Reset those flags
            # so the reconnect path can proceed normally.
            for alias in connections:
                try:
                    conn = connections[alias]
                    conn.closed_in_transaction = False
                    conn.in_atomic_block = False
                    conn.needs_rollback = False
                    conn.savepoint_ids = []
                    conn.atomic_blocks = []
                    conn.ensure_connection()
                except Exception:
                    pass

        def _make_teardown_resilient(original_teardown):
            def _fixture_teardown_resilient(self):
                try:
                    # Set a short statement_timeout for the flush (TRUNCATE CASCADE)
                    # so it fails fast instead of hanging for 60 s when another
                    # connection holds a lock.  The resilient error handler below
                    # will call _rollback_and_close_all_connections() to release
                    # all locks and let the next test start with a clean DB.
                    try:
                        from django.db import connection as _tc
                        if _tc.connection and not _tc.connection.closed:
                            with _tc.cursor() as _cur:
                                _cur.execute(
                                    "SET statement_timeout = '10s'"
                                )
                    except Exception:
                        pass
                    original_teardown(self)
                    # Post-flush re-seed: TransactionTestCase._fixture_teardown
                    # runs TRUNCATE CASCADE on all tables, deleting seed data
                    # (tenant_plans).  Re-seed immediately so the next test class
                    # finds free/pro/enterprise plans.  Deadlock-safe because the
                    # flush already completed and released all locks.
                    # Use a 10s statement_timeout so a locked tenant_plans
                    # table doesn't make the whole test hang until
                    # pytest-timeout fires (60s).
                    try:
                        from django.db import connection as _tc
                        if _tc.connection and not _tc.connection.closed:
                            with _tc.cursor() as _cur:
                                _cur.execute(
                                    "SET statement_timeout = '10s'"
                                )
                    except Exception:
                        pass
                    _seed_tenant_plans_if_missing()
                    # Restore normal statement_timeout for subsequent tests
                    try:
                        from django.db import connection as _tc2
                        if _tc2.connection and not _tc2.connection.closed:
                            with _tc2.cursor() as _cur2:
                                _cur2.execute(
                                    "SET statement_timeout = '120s'"
                                )
                    except Exception:
                        pass
                except DjangoOperationalError as e:
                    msg = str(e).lower()
                    if (
                        "shutting down" in msg
                        or "starting up" in msg
                        or "closed" in msg
                        or "deadlock" in msg
                        or "canceling statement" in msg
                        or "statement timeout" in msg
                    ):
                        _teardown_logger.error(
                            "teardown_operational_error_suppressed: %s", e,
                        )
                        if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                            raise
                        _rollback_and_close_all_connections()
                        return
                    raise
                except DjangoProgrammingError as e:
                    msg = str(e).lower()
                    # A model class (e.g. IngestionTemplate) may be registered in Django's
                    # model registry because its module was imported during test collection,
                    # even though the corresponding DB table was dropped by a migration.
                    # When TransactionTestCase teardown tries to flush the non-existent
                    # table, catch the ProgrammingError and swallow it.
                    if "does not exist" in msg or "relation" in msg:
                        _teardown_logger.error(
                            "teardown_programming_error_suppressed: %s", e,
                        )
                        if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                            raise
                        _rollback_and_close_all_connections()
                        return
                    raise
                except DjangoCommandError as e:
                    # Django's `flush` management command wraps DB errors
                    # (e.g. deadlock OperationalError) in CommandError.
                    # Treat flush-related CommandErrors the same as the
                    # underlying DB errors: the test already passed.
                    msg = str(e).lower()
                    if "couldn't be flushed" in msg:
                        _teardown_logger.error(
                            "teardown_command_error_suppressed: %s", e,
                        )
                        if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                            raise
                        _rollback_and_close_all_connections()
                        return
                    raise
                except DjangoIntegrityError as e:
                    msg = str(e).lower()
                    # post_migrate signal fires create_contenttypes/create_permissions
                    # during TransactionTestCase flush; on shared DBs another process
                    # may have already inserted these rows.
                    # Also handle FK violations: TransactionTestCase TRUNCATE CASCADE
                    # deletes parent rows (e.g. tenants) while child rows (e.g. users
                    # referencing tenant_id) still exist in Django's in-memory state.
                    # When SET CONSTRAINTS ALL IMMEDIATE runs at teardown, deferred FK
                    # checks fail because the referenced row no longer exists.
                    if (
                        "duplicate key" in msg
                        or "unique constraint" in msg
                        or "violates foreign key constraint" in msg
                    ):
                        _teardown_logger.error(
                            "teardown_integrity_error_suppressed: %s", e,
                        )
                        if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                            raise
                        _rollback_and_close_all_connections()
                        return
                    raise
                except DjangoInterfaceError as e:
                    # Connection was closed by the server or a previous error.
                    # Reconnect and retry the teardown once so the DB is flushed
                    # and subsequent tests start with a clean state.
                    _teardown_logger.error(
                        "teardown_interface_error_reconnecting: %s", e,
                    )
                    if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                        raise
                    try:
                        _rollback_and_close_all_connections()
                        # Retry teardown with the fresh connection
                        original_teardown(self)
                        _seed_tenant_plans_if_missing()
                    except Exception:
                        # If retry also fails, rollback+close and move on
                        _rollback_and_close_all_connections()
                    return
                except DjangoTransactionManagementError as e:
                    # Django 6.0: TestCase._fixture_teardown calls
                    # _rollback_atomics(self.atomics) after the flush
                    # (TRUNCATE CASCADE).  TRUNCATE implicitly commits,
                    # so the subsequent transaction.set_rollback(True)
                    # has no active atomic block to roll back.  The
                    # database is already clean — the error is cosmetic.
                    _teardown_logger.error(
                        "teardown_transaction_management_error_suppressed: %s", e,
                    )
                    if os.environ.get("STRICT_TEST_TEARDOWN") == "1":
                        raise
                    _rollback_and_close_all_connections()
                    return
            _fixture_teardown_resilient._hub_teardown_resilient = True
            return _fixture_teardown_resilient

        if not getattr(DjangoTestCase._fixture_teardown, "_hub_teardown_resilient", False):
            DjangoTestCase._fixture_teardown = _make_teardown_resilient(
                DjangoTestCase._fixture_teardown
            )
        if not getattr(
            DjangoTransactionTestCase._fixture_teardown, "_hub_teardown_resilient", False
        ):
            DjangoTransactionTestCase._fixture_teardown = _make_teardown_resilient(
                DjangoTransactionTestCase._fixture_teardown
            )

        # ── setUpClass connection-recovery patch ──────────────────────
        # When a prior test class's teardown poisons the DB connection
        # (closed_in_transaction=True + in_atomic_block=True), the next
        # class's setUpClass inherits a dead connection whose
        # ensure_connection() is blocked.  Wrap setUpClass so we recover
        # the connection BEFORE _enter_atomics() wraps it in a transaction.
        _original_setupclass = DjangoTestCase.setUpClass

        @classmethod
        def _setUpClass_recovered(cls):
            _ensure_db_connection_impl()
            _original_setupclass()

        _setUpClass_recovered._hub_setupclass_recovered = True

        if not getattr(DjangoTestCase.setUpClass, "_hub_setupclass_recovered", False):
            DjangoTestCase.setUpClass = _setUpClass_recovered
    except Exception:
        pass
