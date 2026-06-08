"""285.14.3.6 — Verify RLS policy coverage for scheduled_export app."""
import pytest
import os
import re

from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_SE_MODELS = {
    "scheduled_exports": "ScheduledExport",
    "scheduled_export_runs": "ScheduledExportRun",
    "export_run_costs": "ExportRunCost",
}


def _migration_texts(app_dir):
    mig_dir = os.path.join(app_dir, "migrations")
    texts = {}
    if not os.path.isdir(mig_dir):
        return texts
    for fname in sorted(os.listdir(mig_dir)):
        if fname.startswith("_") or not fname.endswith(".py"):
            continue
        with open(os.path.join(mig_dir, fname), encoding="utf-8", errors="ignore") as f:
            texts[fname] = f.read()
    return texts


class ScheduledExportRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.scheduled_export
        app_dir = os.path.dirname(hub.apps.scheduled_export.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_all_tenant_scoped_models_have_rls(self):
        all_content = "\n".join(self.migrations.values())
        missing = []
        for table, model_name in _SE_MODELS.items():
            if not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ):
                missing.append(f"{model_name} ({table})")
        assert not missing, (
            f"Scheduled export models missing RLS policies: {missing}"
        )

    @pytest.mark.integration
    def test_all_three_models_individually_covered(self):
        all_content = "\n".join(self.migrations.values())
        for table in _SE_MODELS:
            assert re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ), f"{table} RLS policy not found"

    @pytest.mark.integration
    def test_rls_kill_switch_present(self):
        all_content = "\n".join(self.migrations.values())
        assert "current_setting('app.rls_" in all_content
        assert "app.current_tenant_id" in all_content
