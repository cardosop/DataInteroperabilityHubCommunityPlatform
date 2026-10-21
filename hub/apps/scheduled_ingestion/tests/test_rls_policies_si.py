"""285.14.3.5 — Verify RLS policy coverage for scheduled_ingestion app."""

import os
import re

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_SI_MODELS = {
    "scheduled_ingestions": "ScheduledIngestion",
}
# ScheduledIngestionRun inherits tenant scoping through ScheduledIngestion FK;
# no direct tenant_id column — RLS not applicable.


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


class ScheduledIngestionRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.scheduled_ingestion

        app_dir = os.path.dirname(hub.apps.scheduled_ingestion.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_all_tenant_scoped_models_have_rls(self):
        all_content = "\n".join(self.migrations.values())
        missing = []
        for table, model_name in _SI_MODELS.items():
            if not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content,
                re.IGNORECASE,
            ):
                missing.append(f"{model_name} ({table})")
        assert not missing, f"Scheduled ingestion models missing RLS policies: {missing}"

    @pytest.mark.integration
    def test_known_covered_tables(self):
        all_content = "\n".join(self.migrations.values())
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+scheduled_ingestions",
            all_content,
            re.IGNORECASE,
        )

    @pytest.mark.integration
    def test_scheduled_ingestion_runs_inherits_tenant_scope(self):
        """ScheduledIngestionRun has no direct tenant_id — inherits through parent FK."""
        all_content = "\n".join(self.migrations.values())
        assert not re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+scheduled_ingestion_runs",
            all_content,
            re.IGNORECASE,
        ), "scheduled_ingestion_runs should not have direct RLS"

    @pytest.mark.integration
    def test_non_tenant_models_excluded(self):
        """DeadLetterQueueItem and IngestionCost lack tenant FK — no direct RLS."""
        all_content = "\n".join(self.migrations.values())
        for table in ("scheduled_ingestion_dlq", "scheduled_ingestion_costs"):
            assert not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content,
                re.IGNORECASE,
            ), f"{table} should not have direct RLS (no tenant FK)"
