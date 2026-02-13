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
"""

import sys
from pathlib import Path

import pytest

# Allow hub app tests to import tests.utils.polling (wait_until) when run from hub/ or repo root
_repo_root = Path(__file__).resolve().parents[1]
if _repo_root.exists() and str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def pytest_configure(config):
    """Apply sql_flush CASCADE patch before any hub app tests run."""
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
