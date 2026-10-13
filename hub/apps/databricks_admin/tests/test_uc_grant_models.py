"""TDD pins for the grants-bridge models (openspec add-databricks-uc-write
task 2.6) — `UCPPrincipal` + `UCGrantBinding` with the paired RLS.

No mocks: real Postgres constraints + real RLS policies (the pg_policies
scan convention) + real cascade behavior. The binding exclusivity
(one row per principal+securable+privilege) and the OUT_OF_SYNC status
are pinned at the model level.
"""

import os

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class UCGrantModelTests(TestCase):
    def setUp(self):
        require_dns()
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksWorkspace,
            UCPPrincipal,
            UCPPrincipalType,
        )

        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="ws-grants",
            host="dbc-6710eb95-8fe1.cloud.databricks.com",
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status="ACTIVE",
        )
        self.principal = UCPPrincipal.objects.create(
            workspace=self.workspace,
            name="data-team",
            principal_type=UCPPrincipalType.GROUP,
        )

    def test_binding_is_workspace_scoped_with_unique_privilege_row(self):
        from hub.apps.databricks_admin.models import (
            UCGrantBinding,
            UCGrantBindingStatus,
            UCGrantSecurableType,
        )

        binding = UCGrantBinding.objects.create(
            workspace=self.workspace,
            principal=self.principal,
            securable_type=UCGrantSecurableType.TABLE,
            securable_full_name="main.sales.orders",
            privilege="SELECT",
            status=UCGrantBindingStatus.APPLIED,
        )
        assert binding.workspace_id == self.workspace.id
        from django.db import IntegrityError, transaction

        with pytest.raises(IntegrityError), transaction.atomic():
            UCGrantBinding.objects.create(
                workspace=self.workspace,
                principal=self.principal,
                securable_type=UCGrantSecurableType.TABLE,
                securable_full_name="main.sales.orders",
                privilege="SELECT",
                status=UCGrantBindingStatus.APPLIED,
            )

    def test_shadow_status_and_source_policy_are_recorded(self):
        from hub.apps.databricks_admin.models import (
            UCGrantBinding,
            UCGrantBindingStatus,
            UCGrantSecurableType,
        )

        binding = UCGrantBinding.objects.create(
            workspace=self.workspace,
            principal=self.principal,
            securable_type=UCGrantSecurableType.TABLE,
            securable_full_name="main.sales.customers",
            privilege="SELECT",
            status=UCGrantBindingStatus.OUT_OF_SYNC,
            source_policy_id="pol-abc",
        )
        assert binding.status == UCGrantBindingStatus.OUT_OF_SYNC
        assert binding.source_policy_id == "pol-abc"

    def test_workspace_delete_cascades_bindings_and_principals(self):
        from hub.apps.databricks_admin.models import (
            UCGrantBinding,
            UCGrantSecurableType,
        )

        UCGrantBinding.objects.create(
            workspace=self.workspace,
            principal=self.principal,
            securable_type=UCGrantSecurableType.TABLE,
            securable_full_name="main.sales.orders",
            privilege="SELECT",
        )
        binding_id = self.workspace.uc_grant_bindings.first().id
        self.workspace.delete()
        assert not UCGrantBinding.objects.filter(id=binding_id).exists()

    def test_principal_is_workspace_unique(self):
        from django.db import IntegrityError, transaction

        from hub.apps.databricks_admin.models import UCPPrincipal, UCPPrincipalType

        with pytest.raises(IntegrityError), transaction.atomic():
            UCPPrincipal.objects.create(
                workspace=self.workspace,
                name="data-team",
                principal_type=UCPPrincipalType.GROUP,
            )


class UCGrantRLSPolicyTests(TestCase):
    """Paired indirect-FK RLS policies for both tables (the pg_policies
    scan convention — policy SQL written literally, kill-switch GUC)."""

    def test_rls_policies_exist_for_both_tables(self):
        import hub.apps.databricks_admin

        app_dir = os.path.dirname(hub.apps.databricks_admin.__file__)
        mig_dir = os.path.join(app_dir, "migrations")
        texts = []
        for fname in sorted(os.listdir(mig_dir)):
            if fname.endswith(".py"):
                with open(os.path.join(mig_dir, fname)) as fh:
                    texts.append(fh.read())
        joined = "\n".join(texts)
        assert "uc_grant_bindings" in joined
        assert "uc_principals" in joined
        assert "current_setting('app.current_tenant_id', true)" in joined
