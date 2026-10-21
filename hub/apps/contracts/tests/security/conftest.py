"""
Security test fixtures for ODPS ref resolver tests.

Ensures security_audit_logs table exists before tests that assert on SecurityAuditLog.
When running with TEST_DB_SUFFIX=shared, hub_test_test_shared is used; migrate-test-db
creates it from hub_test template. If the DB was created by Django's test framework
(keepdb path when shared DB was missing), migrations may not have run. Run migrate
when security_audit_logs is missing so tests pass.
"""

import pytest


@pytest.fixture(autouse=True)
def ensure_security_audit_log_table(db):
    """Ensure security_audit_logs exists; run migrate if missing (non-migrated test DB)."""
    from django.core.management import call_command
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_name = 'security_audit_logs'"
        )
        if cursor.fetchone() is None:
            call_command("migrate", "contracts", verbosity=0, run_syncdb=False)
