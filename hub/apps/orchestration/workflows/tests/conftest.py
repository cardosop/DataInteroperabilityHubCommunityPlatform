"""
Orchestration workflow tests conftest — process-cache guard.

With ``--keepdb`` / ``--reuse-db``, the module-level
``_process_workflow_cache`` in ``registry.py`` can hold stale
``WorkflowDefinition`` instances whose DB rows were rolled back by
the previous ``TestCase`` transaction.  Clear it before each test
so ``register_workflow`` always creates or validates the DB row.
"""

import pytest


@pytest.fixture(autouse=True)
def _reset_workflow_definition_cache():
    """Clear the process-wide workflow-definition cache before each test."""
    from hub.apps.orchestration.registry import reset_workflow_definition_cache

    reset_workflow_definition_cache()
    yield
