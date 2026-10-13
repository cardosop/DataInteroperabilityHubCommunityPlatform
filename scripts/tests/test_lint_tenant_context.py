"""Tenant-context linter TDD suite (Phase P.9).

The linter's blind spot: its tenant-access patterns were single-line
substrings like ``.objects.create(tenant`` — a write shaped
``Model.objects.create(\n    tenant_id=...,`` (the semantic signals
pattern) was invisible, so ``hub/apps/semantic/signals.py`` wrote
tenant-scoped ``Job`` rows outside ``tenant_context`` while the linter
reported all-clean. No test pinned the linter at all — this suite does.

Drills run the REAL ``lint_file`` from ``scripts/lint_tenant_context.py``
against synthetic source (no mocks); the final tests pin the REAL
semantic + tenants signal files.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lint_tenant_context import lint_file

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _lint_source(tmp_path: Path, source: str, name: str = "signals.py"):
    fake = tmp_path / "hub" / "apps" / "demo" / name
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text(source, encoding="utf-8")
    return lint_file(str(fake))


class TestTenantIdKwargDetection:
    """The blind spot this phase closes: `tenant_id=` kwarg writes were
    invisible to the pattern set."""

    def test_multiline_create_with_tenant_id_kwarg_is_flagged(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "from django.db import transaction\n\n"
            "def _enqueue():\n"
            "    with transaction.atomic():\n"
            "        job = Job.objects.create(\n"
            "            tenant_id=tenant_id,\n"
            "            type='SNAPSHOT',\n"
            "        )\n",
        )
        assert error is not None, "a tenant_id= kwarg write must be flagged"

    def test_inline_create_with_tenant_id_kwarg_is_flagged(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "def _enqueue():\n    job = Job.objects.create(tenant_id=tenant_id, type='SNAPSHOT')\n",
        )
        assert error is not None

    def test_tenant_id_kwarg_write_inside_tenant_context_passes(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "from hub.apps.tenants.request_tenant import tenant_context\n\n"
            "def _enqueue(*, tenant_id):\n"
            "    with tenant_context(tenant_id):\n"
            "        job = Job.objects.create(\n"
            "            tenant_id=tenant_id,\n"
            "            type='SNAPSHOT',\n"
            "        )\n",
        )
        assert error is None, error

    def test_import_without_usage_is_flagged(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "from hub.apps.tenants.request_tenant import tenant_context\n\n"
            "def _enqueue(*, tenant_id):\n"
            "    job = Job.objects.create(tenant_id=tenant_id)\n",
        )
        assert error is not None
        assert "does NOT wrap" in error

    def test_file_without_tenant_access_is_clean(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "def _helper(x):\n    return x + 1\n",
        )
        assert error is None


class TestRealSignalFiles:
    """The two real files the blind spot protected."""

    def test_semantic_signals_wraps_its_tenant_scoped_job_write(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "semantic" / "signals.py"))
        assert error is None, error

    def test_tenants_signals_wraps_its_tenant_scoped_accesses(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "tenants" / "signals.py"))
        assert error is None, error


class TestWorkerConventionCoverage:
    """The 12.10 discovery hole: worker modules under the repo's
    ``*_jobs``/``*_sync`` conventions were INVISIBLE to the gate (the
    databricks estate's sync workers ride those names). The broadened
    linter must flag and pass them exactly like tasks.py/signals.py."""

    def test_sync_named_file_with_tenant_access_no_context_is_flagged(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "def _ingest():\n    Ledger.objects.create(tenant_id=tid, units=1)\n",
            name="cost_sync.py",
        )
        assert error is not None, (
            "a *_sync.py worker touching tenant data without tenant_context "
            "must be flagged (the discovery-hole class)"
        )

    def test_jobs_named_file_with_tenant_access_no_context_is_flagged(self, tmp_path):
        error = _lint_source(
            tmp_path,
            "def _run():\n    Job.objects.update(tenant_id=tid, status='DONE')\n",
            name="uc_sync_jobs.py",
        )
        assert error is not None

    def test_databricks_cost_sync_wraps_its_tenant_scoped_work(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "databricks_admin" / "cost_sync.py"))
        assert error is None, error

    def test_databricks_uc_sync_wraps_its_tenant_scoped_work(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "databricks_admin" / "uc_sync.py"))
        assert error is None, error

    def test_contracts_lineage_sync_wraps_its_tenant_scoped_work(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "contracts" / "lineage_sync.py"))
        assert error is None, error

    def test_governance_report_scheduler_wraps_its_tenant_scoped_work(self):
        error = lint_file(str(REPO_ROOT / "hub" / "apps" / "governance" / "report_scheduler.py"))
        assert error is None, error

    def test_marketplace_sync_workflow_wraps_its_tenant_scoped_work(self):
        error = lint_file(
            str(REPO_ROOT / "hub" / "apps" / "marketplace" / "workflows" / "marketplace_sync.py")
        )
        assert error is None, error
