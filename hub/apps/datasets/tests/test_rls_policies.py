"""285.14.3.2 — Verify RLS policy coverage for datasets app."""
import pytest
import os
import re

from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_DATASET_MODELS = {
    "datasets": "Dataset",
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


class DatasetsRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.datasets
        app_dir = os.path.dirname(hub.apps.datasets.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_dataset_has_rls_policy(self):
        all_content = "\n".join(self.migrations.values())
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+datasets", all_content, re.IGNORECASE
        ), "Dataset model missing RLS policy"

    @pytest.mark.integration
    def test_no_other_tenant_scoped_models_without_rls(self):
        """DatasetVersion and DatasetRefresh are views/serializers, not models.
        Confirm that only the Dataset table needs RLS."""
        all_content = "\n".join(self.migrations.values())
        for table in _DATASET_MODELS:
            assert re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ), f"{table} RLS policy not found"
