"""285.14.3.7 — Verify RLS policy coverage for mesh app."""

import os
import re

import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)

_MESH_MODELS = {
    "data_mesh_domains": "DataMeshDomain",
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


class MeshRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.mesh

        app_dir = os.path.dirname(hub.apps.mesh.__file__)
        self.migrations = _migration_texts(app_dir)

    @pytest.mark.integration
    def test_data_mesh_domain_has_rls(self):
        all_content = "\n".join(self.migrations.values())
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+data_mesh_domains",
            all_content,
            re.IGNORECASE,
        ), "DataMeshDomain missing RLS policy"

    @pytest.mark.integration
    def test_policy_application_and_compliance_report_no_direct_rls(self):
        """PolicyApplication and ComplianceReport lack tenant FK
        (they reference DataMeshDomain). No direct RLS needed."""
        all_content = "\n".join(self.migrations.values())
        for table in ("policy_applications", "compliance_reports"):
            has_policy = re.search(
                rf"CREATE\s+POLICY\s+\S+\s+ON\s+{table}",
                all_content,
                re.IGNORECASE,
            )
            assert not has_policy, f"{table} has no tenant FK — should not have direct RLS"

    @pytest.mark.integration
    def test_rls_kill_switch_present(self):
        all_content = "\n".join(self.migrations.values())
        assert "current_setting('app.rls_data_mesh_domains_enabled" in all_content
        assert "app.current_tenant_id" in all_content
