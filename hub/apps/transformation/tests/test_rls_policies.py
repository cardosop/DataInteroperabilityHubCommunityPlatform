"""285.14.3.11 — Verify RLS policy coverage for transformation app."""
import pytest
import os
import re

from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_TRANSFORMATION_MODELS = {
    "transformation_pipelines": "TransformationPipeline",
    "wrangling_sessions": "WranglingSession",
    "preview_results": "PreviewResult",
}

# Models WITHOUT direct tenant_id FK (tenant resolved through parent model):
#   - transformation_nodes (via TransformationPipeline)
#   - transformation_pipeline_executions (via TransformationPipeline)
#   - wrangling_operations (via WranglingSession)
# RLS on these models would require subquery-based policies; access control
# is enforced at the parent model level instead.


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


class TransformationRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.transformation
        app_dir = os.path.dirname(hub.apps.transformation.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_all_tenant_scoped_models_have_rls(self):
        all_content = "\n".join(self.migrations.values())
        missing = []
        for table, model_name in _TRANSFORMATION_MODELS.items():
            if not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ):
                missing.append(f"{model_name} ({table})")
        assert not missing, (
            f"Transformation models missing RLS policies: {missing}"
        )

    @pytest.mark.integration
    def test_all_tenant_scoped_models_individually_covered(self):
        """Every model with a direct tenant_id FK must have an RLS policy."""
        all_content = "\n".join(self.migrations.values())
        for table in _TRANSFORMATION_MODELS:
            assert re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ), f"{table} RLS policy not found"

    @pytest.mark.integration
    def test_non_tenant_models_excluded(self):
        """TransformationNode and PipelineExecution lack tenant FK."""
        all_content = "\n".join(self.migrations.values())
        for table in ("transformation_nodes", "transformation_pipeline_executions"):
            assert not re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content, re.IGNORECASE,
            ), f"{table} should not have direct RLS (no tenant FK)"

    @pytest.mark.integration
    def test_rls_kill_switch_present(self):
        all_content = "\n".join(self.migrations.values())
        assert "current_setting('app.rls_" in all_content
        assert "app.current_tenant_id" in all_content
