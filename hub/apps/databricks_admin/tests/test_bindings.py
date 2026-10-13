"""TDD pins for the Hub-user ↔ Databricks-principal binding model
(openspec add-databricks-control-plane task 0b.3).

No mocks: real Postgres (real constraints, real RLS), real tenants/users/
workspaces. The pins cover:

- MODEL: the binding is per (user, workspace) AND per (workspace, sub) —
  exclusivity both ways (one Hub account per principal per workspace, one
  principal per Hub account per workspace); tenant-scoped with a paired
  RLS migration.
- PROVISIONING (first login by (sub, email)): creates on first login,
  idempotent on relogin, updates sub/email on email-continuity relogin,
  and REFUSES to bind a principal that already belongs to a DIFFERENT
  Hub account on the same workspace.
- CROSS-WORKSPACE ISOLATION: the same principal on workspace W2 gets a
  SEPARATE binding row; resolution is workspace-keyed so a W1 binding is
  never resolvable for W2 (the model-level guarantee behind "per-workspace
  tokens never reused across workspaces", consumed by 0b.4/0b.5).
- CHOOSER: sso_workspace_options returns only the tenant's ACTIVE
  workspaces; select_workspace rejects unknown/cross-tenant ids.
"""

import uuid

import pytest
from django.db import IntegrityError, connection, transaction

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests.test_views import (
    _activate_billing,
    _make_user,
)
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _workspace(tenant, **overrides):
    from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace

    return DatabricksWorkspace.objects.create(
        tenant=tenant,
        name=overrides.pop("name", f"ws-{uuid.uuid4().hex[:8]}"),
        host=REAL_HOST,
        cloud=overrides.pop("cloud", DatabricksCloud.AWS),
        region="us-east-1",
        status=overrides.pop("status", "ACTIVE"),
        **overrides,
    )


def _binding(tenant, user, workspace, **overrides):
    from hub.apps.databricks_admin.models import DatabricksUserBinding

    return DatabricksUserBinding.objects.create(
        tenant=tenant,
        user=user,
        workspace=workspace,
        databricks_sub=overrides.pop("databricks_sub", f"sub-{uuid.uuid4().hex[:8]}"),
        databricks_email=overrides.pop("databricks_email", user.email),
        **overrides,
    )


def _setup():
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    admin = _make_user(tenant, f"bind-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN")
    workspace = _workspace(tenant)
    return tenant, admin, workspace


class TestBindingModel:
    def test_unique_per_user_and_workspace(self):
        tenant, admin, workspace = _setup()
        _binding(tenant, admin, workspace)
        with pytest.raises(IntegrityError), transaction.atomic():
            _binding(tenant, admin, workspace)

    def test_unique_principal_per_workspace(self):
        tenant, admin, workspace = _setup()
        other_user = _make_user(tenant, f"other-{uuid.uuid4().hex[:8]}@test.com")
        _binding(tenant, admin, workspace, databricks_sub="sub-shared")
        with pytest.raises(IntegrityError), transaction.atomic():
            _binding(tenant, other_user, workspace, databricks_sub="sub-shared")

    def test_same_principal_different_workspace_is_a_separate_row(self):
        tenant, admin, workspace = _setup()
        second = _workspace(tenant)
        first = _binding(tenant, admin, workspace, databricks_sub="sub-cross")
        second_binding = _binding(tenant, admin, second, databricks_sub="sub-cross")
        assert first.id != second_binding.id
        assert first.workspace_id != second_binding.workspace_id

    def test_rls_policy_migration_exists_for_the_table(self):
        """CLAUDE.md RLS contract — the paired policy migration ships with
        the model, not later."""
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM pg_policies WHERE schemaname = 'public' "
                "AND tablename = 'databricks_user_bindings'"
            )
            assert cursor.fetchone() is not None, "databricks_user_bindings lacks an RLS policy"


class TestProvisioning:
    def test_first_login_creates_binding_with_sub_and_email(self):
        from hub.apps.databricks_admin.bindings import provision_binding

        tenant, admin, workspace = _setup()
        binding = provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-first",
            databricks_email="dbx-user@databricks.com",
        )
        assert binding.databricks_sub == "sub-first"
        assert binding.databricks_email == "dbx-user@databricks.com"
        assert binding.workspace_id == workspace.id
        assert binding.user_id == admin.id

    def test_relogin_is_idempotent_and_updates_email(self):
        from hub.apps.databricks_admin.bindings import provision_binding

        tenant, admin, workspace = _setup()
        first = provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-stable",
            databricks_email="old@databricks.com",
        )
        again = provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-stable",
            databricks_email="new@databricks.com",
        )
        assert again.id == first.id
        again.refresh_from_db()
        assert again.databricks_email == "new@databricks.com"

    def test_principal_bound_to_another_hub_account_is_refused(self):
        from hub.apps.databricks_admin.bindings import (
            DatabricksBindingConflict,
            provision_binding,
        )

        tenant, admin, workspace = _setup()
        other = _make_user(tenant, f"impersonate-{uuid.uuid4().hex[:8]}@test.com")
        provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-owned",
            databricks_email="owner@databricks.com",
        )
        with pytest.raises(DatabricksBindingConflict) as excinfo:
            provision_binding(
                tenant=tenant,
                user=other,
                workspace=workspace,
                databricks_sub="sub-owned",
                databricks_email="owner@databricks.com",
            )
        assert "another" in str(excinfo.value).lower()

    def test_provisioning_rejects_cross_tenant_user(self):
        # A caller passing a FOREIGN-tenant user (tenant A user, tenant B
        # workspace) must be refused — otherwise a cross-tenant binding row
        # would be created and made RLS-visible under the wrong tenant.
        from hub.apps.databricks_admin.bindings import provision_binding

        tenant, _admin, workspace = _setup()
        other_tenant = TenantFactory.create_tenant()
        foreign_user = _make_user(other_tenant, f"foreign-{uuid.uuid4().hex[:8]}@test.com")

        with pytest.raises(ValueError, match="tenant"):
            provision_binding(
                tenant=tenant,
                user=foreign_user,
                workspace=workspace,
                databricks_sub="sub-foreign",
                databricks_email="foreign@databricks.com",
            )
        from hub.apps.databricks_admin.models import DatabricksUserBinding

        assert not DatabricksUserBinding.objects.filter(workspace=workspace).exists(), (
            "no cross-tenant binding row may be created"
        )

    def test_email_continuity_with_different_sub_updates_the_binding(self):
        """The same human (same Hub user) with a re-created Databricks
        principal: the (user, workspace) key wins and the sub is updated —
        the email is how Hub accounts match."""
        from hub.apps.databricks_admin.bindings import provision_binding

        tenant, admin, workspace = _setup()
        first = provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-old",
            databricks_email="person@databricks.com",
        )
        again = provision_binding(
            tenant=tenant,
            user=admin,
            workspace=workspace,
            databricks_sub="sub-new",
            databricks_email="person@databricks.com",
        )
        assert again.id == first.id
        again.refresh_from_db()
        assert again.databricks_sub == "sub-new"


class TestCrossWorkspaceIsolation:
    def test_resolution_is_workspace_keyed(self):
        from hub.apps.databricks_admin.bindings import resolve_binding

        tenant, admin, workspace = _setup()
        second = _workspace(tenant)
        _binding(tenant, admin, workspace, databricks_sub="sub-iso")

        assert resolve_binding(user=admin, workspace=workspace) is not None
        assert resolve_binding(user=admin, workspace=second) is None, (
            "a W1 binding must never be resolvable for W2"
        )


class TestWorkspaceChooser:
    def test_options_are_tenant_scoped_and_active_only(self):
        from hub.apps.databricks_admin.bindings import sso_workspace_options

        tenant, _admin, workspace = _setup()
        _workspace(tenant, status="REGISTERED")
        _workspace(tenant, status="DISABLED")
        other_tenant = TenantFactory.create_tenant()
        _workspace(other_tenant)

        options = sso_workspace_options(tenant)
        assert [w.id for w in options] == [workspace.id]

    def test_select_rejects_cross_tenant_workspace(self):
        from hub.apps.databricks_admin.bindings import select_workspace
        from hub.apps.databricks_admin.models import DatabricksWorkspace

        tenant, _admin, _ws = _setup()
        other_tenant = TenantFactory.create_tenant()
        foreign = _workspace(other_tenant)

        with pytest.raises(DatabricksWorkspace.DoesNotExist):
            select_workspace(tenant=tenant, workspace_id=foreign.id)

    def test_select_returns_owned_workspace(self):
        from hub.apps.databricks_admin.bindings import select_workspace

        tenant, _admin, workspace = _setup()
        assert select_workspace(tenant=tenant, workspace_id=workspace.id).id == workspace.id


class TestGCPFallbackChooser:
    """0b.8 — GCP workspaces are excluded from the SSO chooser (U2M
    unsupported there)."""

    def test_options_exclude_gcp_workspaces(self):
        from hub.apps.databricks_admin.bindings import sso_workspace_options
        from hub.apps.databricks_admin.models import DatabricksCloud

        tenant, _admin, workspace = _setup()
        _workspace(tenant, cloud=DatabricksCloud.GCP)

        options = sso_workspace_options(tenant)
        assert [w.id for w in options] == [workspace.id]
        assert all(w.cloud != DatabricksCloud.GCP for w in options)
