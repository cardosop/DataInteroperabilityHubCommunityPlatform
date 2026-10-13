"""P0 (openspec add-databricks-control-plane task 0.2) — DatabricksWorkspace model + RLS.

No mocks: the model tests run against the real Postgres test database
(django_db applies the actual migrations, including the RLS RunSQL);
the RLS coverage tests scan the migration files for the policy, the
kill-switch GUC, and the reverse SQL — the same 285.14.3.8 pattern as
``hub/apps/billing/tests/test_rls_policies.py``.
"""

import os
import re

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class DatabricksWorkspaceModelTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.other_tenant = TenantFactory.create_tenant()

    def _create(self, tenant, name="prod", host=REAL_HOST, **kwargs):
        kwargs.setdefault("cloud", DatabricksCloud.AWS)
        kwargs.setdefault("region", "us-east-1")
        return DatabricksWorkspace.objects.create(tenant=tenant, name=name, host=host, **kwargs)

    def test_create_defaults_status_registered_and_auto_fields(self):
        ws = self._create(self.tenant)
        assert ws.status == DatabricksWorkspaceStatus.REGISTERED
        assert ws.id is not None  # UUID pk auto-assigned on save
        assert ws.created_at is not None
        assert ws.updated_at is not None

    def test_str_representation(self):
        ws = self._create(self.tenant, name="prod", host=REAL_HOST)
        assert str(ws) == f"DatabricksWorkspace prod ({REAL_HOST})"

    def test_unique_name_per_tenant(self):
        self._create(self.tenant, name="prod")
        # Same name in a DIFFERENT tenant is allowed.
        self._create(self.other_tenant, name="prod", host=REAL_HOST)
        # Same name in the SAME tenant violates the unique constraint.
        with pytest.raises(IntegrityError):
            self._create(self.tenant, name="prod", host=REAL_HOST)

    def test_invalid_cloud_rejected_by_full_clean(self):
        ws = DatabricksWorkspace(
            tenant=self.tenant,
            name="bad-cloud",
            host=REAL_HOST,
            cloud="ORACLE",
            region="us-east-1",
        )
        with pytest.raises(ValidationError):
            ws.full_clean()

    def test_metastore_id_is_optional(self):
        ws = self._create(self.tenant, name="no-metastore")
        assert ws.metastore_id is None

    def test_status_and_cloud_choices_match_spec(self):
        # P0 spec: status REGISTERED/CONNECTING/ACTIVE/ERROR/DISABLED;
        # cloud AWS/AZURE/GCP.
        assert set(DatabricksWorkspaceStatus.values) == {
            "REGISTERED",
            "CONNECTING",
            "ACTIVE",
            "ERROR",
            "DISABLED",
        }
        assert set(DatabricksCloud.values) == {"AWS", "AZURE", "GCP"}


class DatabricksWorkspaceRLSPolicyTests(TestCase):
    def setUp(self):
        import hub.apps.databricks_admin

        app_dir = os.path.dirname(hub.apps.databricks_admin.__file__)
        mig_dir = os.path.join(app_dir, "migrations")
        texts = []
        for fname in sorted(os.listdir(mig_dir)):
            if not fname.endswith(".py") or fname.startswith("_"):
                continue
            with open(os.path.join(mig_dir, fname), encoding="utf-8") as fh:
                texts.append(fh.read())
        self.migration_text = "\n".join(texts)

    def test_rls_policy_created_for_databricks_workspaces(self):
        assert re.search(
            r"CREATE\s+POLICY\s+\S+\s+ON\s+databricks_workspaces",
            self.migration_text,
            re.IGNORECASE,
        ), "databricks_workspaces must ship a paired RLS policy (CLAUDE.md contract)"

    def test_rls_kill_switch_and_tenant_guc_present(self):
        # Feature-flag guard pattern (audit 0005): USING passes when the
        # rls_<table>_enabled kill switch is explicitly off; otherwise the
        # row must match app.current_tenant_id.
        assert "current_setting('app.rls_databricks_workspaces_enabled'" in self.migration_text
        assert "app.current_tenant_id" in self.migration_text

    def test_reverse_sql_drops_policy_and_disables_rls(self):
        assert (
            "DROP POLICY IF EXISTS tenant_isolation ON databricks_workspaces" in self.migration_text
        )
        assert "ALTER TABLE databricks_workspaces DISABLE ROW LEVEL SECURITY" in self.migration_text


class DatabricksWorkspacePartialSaveTests(TestCase):
    """Status-only saves must not re-run host DNS validation (0.8 review)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()

    def test_save_update_fields_excluding_host_skips_dns_validation(self):
        ws = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="partial-save",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        # In-memory mutation to a bogus host — a status-only save must NOT
        # re-resolve the host (soft-delete on a decommissioned host must
        # still work).
        ws.host = "localhost.cloud.databricks.com"
        ws.save(update_fields=["status"])
        ws.refresh_from_db()
        assert ws.host == REAL_HOST, "status-only save must not rewrite the host"


class DatabricksWorkspaceTransitionTests(TestCase):
    """transition_to() — billing Subscription pattern (task 0.20)."""

    def setUp(self):
        require_dns()  # workspace save() validates the host through real DNS
        self.tenant = TenantFactory.create_tenant()

    def _create_with_status(self, status, name=None):
        return DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name=name or f"ws-{status.value}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=status,
        )

    def test_registered_to_active_on_successful_probe(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.REGISTERED)
        assert ws.transition_to(DatabricksWorkspaceStatus.ACTIVE) is True
        assert ws.status == DatabricksWorkspaceStatus.ACTIVE

    def test_registered_to_connecting_reserves_async_probe_path(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.REGISTERED)
        assert ws.transition_to(DatabricksWorkspaceStatus.CONNECTING) is True
        assert ws.status == DatabricksWorkspaceStatus.CONNECTING

    def test_connecting_completes_to_active_or_error(self):
        for target in (DatabricksWorkspaceStatus.ACTIVE, DatabricksWorkspaceStatus.ERROR):
            with self.subTest(target=target):
                ws = self._create_with_status(
                    DatabricksWorkspaceStatus.CONNECTING,
                    name=f"ws-connecting-{target.value}",
                )
                assert ws.transition_to(target) is True
                assert ws.status == target

    def test_error_retest_to_active(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.ERROR)
        assert ws.transition_to(DatabricksWorkspaceStatus.ACTIVE) is True
        assert ws.status == DatabricksWorkspaceStatus.ACTIVE

    def test_active_to_error(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.ACTIVE)
        assert ws.transition_to(DatabricksWorkspaceStatus.ERROR) is True
        assert ws.status == DatabricksWorkspaceStatus.ERROR

    def test_soft_disable_from_any_live_status(self):
        for start in (
            DatabricksWorkspaceStatus.REGISTERED,
            DatabricksWorkspaceStatus.CONNECTING,
            DatabricksWorkspaceStatus.ACTIVE,
            DatabricksWorkspaceStatus.ERROR,
        ):
            with self.subTest(start=start):
                ws = self._create_with_status(start, name=f"ws-disable-{start.value}")
                assert ws.transition_to(DatabricksWorkspaceStatus.DISABLED) is True
                assert ws.status == DatabricksWorkspaceStatus.DISABLED

    def test_noop_same_status_returns_false(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.ACTIVE)
        assert ws.transition_to(DatabricksWorkspaceStatus.ACTIVE) is False
        assert ws.status == DatabricksWorkspaceStatus.ACTIVE

    def test_invalid_transition_raises_with_code(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.DISABLED)
        with pytest.raises(ValidationError) as exc_info:
            ws.transition_to(DatabricksWorkspaceStatus.ACTIVE)
        assert exc_info.value.code == "invalid_workspace_status_transition"
        assert ws.status == DatabricksWorkspaceStatus.DISABLED

    def test_disabled_is_terminal(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.DISABLED)
        for target in (
            DatabricksWorkspaceStatus.REGISTERED,
            DatabricksWorkspaceStatus.CONNECTING,
            DatabricksWorkspaceStatus.ACTIVE,
            DatabricksWorkspaceStatus.ERROR,
        ):
            with self.subTest(target=target), pytest.raises(ValidationError):
                ws.transition_to(target)
        assert ws.status == DatabricksWorkspaceStatus.DISABLED

    def test_transition_does_not_persist_without_save(self):
        ws = self._create_with_status(DatabricksWorkspaceStatus.REGISTERED)
        ws.transition_to(DatabricksWorkspaceStatus.ACTIVE)
        assert (
            DatabricksWorkspace.objects.get(pk=ws.pk).status == DatabricksWorkspaceStatus.REGISTERED
        )
        ws.save()
        ws.refresh_from_db()
        assert ws.status == DatabricksWorkspaceStatus.ACTIVE
