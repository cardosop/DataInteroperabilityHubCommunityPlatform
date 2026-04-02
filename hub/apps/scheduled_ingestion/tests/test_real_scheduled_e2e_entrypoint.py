"""
Real scheduled ingestion/export E2E entrypoint tests.

These tests run only when REAL_SCHEDULED_E2E=1. They do not use mocks; any test
here that performs data transfer uses real storage/credentials per
docs/runbooks/REAL_SCHEDULED_INGESTION_EXPORT_E2E.md.

Run with:
  REAL_SCHEDULED_E2E=1 pytest hub/apps/scheduled_ingestion/tests/test_real_scheduled_e2e_entrypoint.py -v

Exclude from default runs:
  pytest -m 'not real_scheduled_e2e'
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.slow

pytestmark = [
    pytest.mark.real_scheduled_e2e,
    pytest.mark.django_db,
]


def _repo_root():
    """Return repo root (directory containing hub/ and docs/)."""
    path = Path(__file__).resolve()
    for p in path.parents:
        if (p / "hub").is_dir() and (p / "docs").is_dir():
            return p
    # Fallback when not under standard layout (e.g. installed package)
    return path.parents[4] if len(path.parents) > 4 else path.parent


def test_runbook_exists_when_real_e2e_enabled():
    """
    When REAL_SCHEDULED_E2E=1, the real E2E runbook must exist.

    This test is only collected when REAL_SCHEDULED_E2E=1 (see conftest
    pytest_collection_modifyitems). It verifies the documented entrypoint
    (runbook) is in place for running real scheduled ingestion/export tests
    against real storage and credentials.
    """
    root = _repo_root()
    runbook = root / "docs" / "runbooks" / "REAL_SCHEDULED_INGESTION_EXPORT_E2E.md"
    assert runbook.is_file(), (
        f"Runbook missing: {runbook}. See docs/runbooks/REAL_SCHEDULED_INGESTION_EXPORT_E2E.md"
    )
    content = runbook.read_text()
    assert "REAL_SCHEDULED_E2E" in content
    assert "real_scheduled_e2e" in content
    assert "S3" in content and "GCS" in content and "AZURE_BLOB" in content


def test_env_guard_set_when_real_e2e_run():
    """
    When this test runs, REAL_SCHEDULED_E2E must be 1 (guard enforced at collection).
    """
    assert os.environ.get("REAL_SCHEDULED_E2E", "").strip() == "1", (
        "real_scheduled_e2e tests should only run when REAL_SCHEDULED_E2E=1"
    )
