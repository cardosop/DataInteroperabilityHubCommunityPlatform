"""
Orchestration test conftest — cleanup fixtures for --reuse-db compatibility.

With --reuse-db tests commit data that persists across
runs.  WorkflowDefinition has a unique constraint on (name, version), so
tests that call WorkflowDefinition.objects.create() fail with
ValidationError on the second run because the record already exists.

This autouse fixture deletes stale WorkflowInstance and WorkflowDefinition
rows before each test, ensuring a clean slate without requiring changes to
every individual test file.
"""

import pytest


@pytest.fixture(autouse=True)
def _clean_stale_workflow_data():
    """Remove stale workflow definitions/instances before each test.

    WorkflowInstance has a PROTECTED FK to WorkflowDefinition, so
    instances must be deleted first.  Runs before each test so setUp
    calls to WorkflowDefinition.objects.create() don't hit
    UniqueConstraint violations from previous --reuse-db runs.

    Wrapped in transaction.atomic() (SAVEPOINT) so that if the
    cleanup fails (e.g., table locked), only the savepoint is rolled
    back — the outer TestCase transaction stays clean and the test
    doesn't cascade-fail with InFailedSqlTransaction.
    """
    try:
        from django.db import transaction
        from hub.apps.orchestration.models import (
            WorkflowDefinition,
            WorkflowInstance,
        )

        with transaction.atomic():
            WorkflowInstance.objects.all().delete()
            WorkflowDefinition.objects.all().delete()
    except Exception:
        # Cleanup failed (table locked, connection broken, etc.).
        # The savepoint was rolled back so the outer transaction is
        # still clean.  If stale data causes a UniqueConstraint
        # violation in setUp, that test will fail with a clear error.
        pass
    yield
