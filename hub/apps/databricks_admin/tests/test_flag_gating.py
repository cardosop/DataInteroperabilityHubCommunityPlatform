"""P0 (openspec add-databricks-control-plane task 0.12) — feature-flag gating.

Real DB, real flags, real 403s:

- ``databricks_control_plane_enabled`` (Tenant boolean, default-off for new
  AND existing tenants, DRAFT registry entry) gates EVERY control-plane
  endpoint with ``DATABRICKS_CONTROL_PLANE_DISABLED``.
- the emergency kill switch (separate Tenant boolean) returns
  ``DATABRICKS_WORKSPACES_DISABLED`` even when the flag is on.
- the warehouses app's Databricks path is gated by the pre-existing
  ``warehouse_databricks_enabled`` field (``WAREHOUSE_TYPE_DISABLED_FOR_TENANT``).
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin.models import DatabricksCloud, DatabricksWorkspace
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.tenants import feature_flag_registry
from hub.apps.users.models import Role, User, UserRole
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

WORKSPACES_URL = "/api/v1/databricks/workspaces/"


def _activate_billing(tenant):
    """Active BASE subscription — the billing middleware gates POST/PATCH/DELETE.

    Delegates to the shared helper in tenants' test factories: importing
    billing directly here was a GATE-29 boundary violation (the billing
    import lives at the ONE allowlisted + guarded site, 313.H.3 — 1.3
    review fix).
    """
    from hub.apps.tenants.tests.factories import activate_billing

    activate_billing(tenant)


def _make_admin(tenant):
    email = f"{uuid.uuid4().hex[:8]}-flag-admin@test.com"
    user = User.objects.create_user(email=email, password="testpass123", tenant=tenant)
    role, _ = Role.objects.get_or_create(tenant=tenant, name="TENANT_ADMIN")
    UserRole.objects.get_or_create(user=user, role=role)
    return user


def _api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _payload():
    return {
        "name": "prod",
        "host": REAL_HOST,
        "cloud": DatabricksCloud.AWS,
        "region": "us-east-1",
    }


class FlagRegistryTests(TestCase):
    def test_control_plane_flag_registered_as_draft_default_off(self):
        flag = feature_flag_registry.get_flag("databricks_control_plane_enabled")
        assert flag is not None, "flag must be registered in the lifecycle registry"
        assert flag.stage == "DRAFT"
        assert flag.default_new_tenants is False
        assert flag.default_existing_tenants is False

    def test_tenant_field_defaults_false(self):
        tenant = TenantFactory.create_tenant()
        tenant.refresh_from_db()
        assert tenant.databricks_control_plane_enabled is False
        assert tenant.databricks_workspaces_kill_switch is False


class ControlPlaneGateTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_admin(self.tenant)

    def test_flag_off_returns_403_control_plane_disabled(self):
        response = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_CONTROL_PLANE_DISABLED"

    def test_flag_on_allows_create(self):
        self.tenant.databricks_control_plane_enabled = True
        self.tenant.save(update_fields=["databricks_control_plane_enabled"])
        response = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 201, response.content

    def test_kill_switch_wins_over_flag(self):
        self.tenant.databricks_control_plane_enabled = True
        self.tenant.databricks_workspaces_kill_switch = True
        self.tenant.save(
            update_fields=["databricks_control_plane_enabled", "databricks_workspaces_kill_switch"]
        )
        response = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_WORKSPACES_DISABLED"

    def test_kill_switch_also_gates_reads(self):
        self.tenant.databricks_workspaces_kill_switch = True
        self.tenant.save(update_fields=["databricks_workspaces_kill_switch"])
        response = _api_client(self.admin).get(WORKSPACES_URL)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_WORKSPACES_DISABLED"


class CredentialGateTests(TestCase):
    """0.12 review — the nested credential endpoints are registry endpoints
    and MUST carry the same flag + kill-switch gate as the workspace CRUD."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.tenant.databricks_control_plane_enabled = True
        self.tenant.save(update_fields=["databricks_control_plane_enabled"])
        self.admin = _make_admin(self.tenant)
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        self.credentials_url = f"/api/v1/databricks/workspaces/{self.workspace.id}/credentials/"

    def test_flag_off_gates_credential_endpoints(self):
        self.tenant.databricks_control_plane_enabled = False
        self.tenant.save(update_fields=["databricks_control_plane_enabled"])
        response = _api_client(self.admin).get(self.credentials_url)
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_CONTROL_PLANE_DISABLED"

    def test_kill_switch_gates_credential_endpoints(self):
        self.tenant.databricks_workspaces_kill_switch = True
        self.tenant.save(update_fields=["databricks_workspaces_kill_switch"])
        response = _api_client(self.admin).post(
            self.credentials_url,
            {"auth_mode": "PAT", "config": {"token": "dapi-x"}},
            format="json",
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "DATABRICKS_WORKSPACES_DISABLED"

    def test_flag_on_allows_credential_list(self):
        response = _api_client(self.admin).get(self.credentials_url)
        assert response.status_code == 200


class SSOOBOGateTests(TestCase):
    """0b.10 — databricks_sso_enabled / databricks_obo_enabled flags +
    kill switches (DRAFT, default-off); flips audited."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_admin(self.tenant)

    def _request(self):
        from rest_framework.request import Request
        from rest_framework.test import APIRequestFactory

        drf_request = Request(APIRequestFactory().get("/api/v1/test/"))
        drf_request.user = self.admin
        drf_request.tenant = self.tenant
        return drf_request

    def test_fields_default_false_on_new_tenants(self):
        fresh = TenantFactory.create_tenant()
        assert fresh.databricks_sso_enabled is False
        assert fresh.databricks_obo_enabled is False
        assert fresh.databricks_sso_kill_switch is False
        assert fresh.databricks_obo_kill_switch is False

    def test_registry_entries_draft_and_default_off(self):
        registry = {entry.name: entry for entry in feature_flag_registry.REGISTRY}
        for name in ("databricks_sso_enabled", "databricks_obo_enabled"):
            entry = registry.get(name)
            assert entry is not None, f"{name} missing from the flag registry"
            assert entry.stage == "DRAFT"
            assert entry.default_new_tenants is False
            assert entry.default_existing_tenants is False

    def test_sso_flag_off_raises_403_code(self):
        from hub.apps.tenants.kill_switch_gates import (
            DatabricksSSODisabledAPIException,
            ensure_databricks_sso_allowed,
        )

        with pytest.raises(DatabricksSSODisabledAPIException) as excinfo:
            ensure_databricks_sso_allowed(self._request())
        assert excinfo.value.code == "DATABRICKS_SSO_DISABLED"

    def test_obo_flag_off_raises_403_code(self):
        from hub.apps.tenants.kill_switch_gates import (
            DatabricksOBODisabledAPIException,
            ensure_databricks_obo_allowed,
        )

        with pytest.raises(DatabricksOBODisabledAPIException) as excinfo:
            ensure_databricks_obo_allowed(self._request())
        assert excinfo.value.code == "DATABRICKS_OBO_DISABLED"

    def test_flag_on_passes_and_kill_switch_wins(self):
        from hub.apps.tenants.kill_switch_gates import (
            DatabricksSSODisabledAPIException,
            ensure_databricks_sso_allowed,
        )

        self.tenant.databricks_sso_enabled = True
        self.tenant.save(update_fields=["databricks_sso_enabled"])
        ensure_databricks_sso_allowed(self._request())  # must not raise

        self.tenant.databricks_sso_kill_switch = True
        self.tenant.save(update_fields=["databricks_sso_kill_switch"])
        with pytest.raises(DatabricksSSODisabledAPIException):
            ensure_databricks_sso_allowed(self._request())

    def test_flag_flip_is_audited_with_before_after(self):
        """Flipping through the REAL feature-flags endpoint persists the
        field AND emits TENANT_FEATURE_FLAG_UPDATED with before/after."""
        from hub.apps.audit.models import AuditEvent

        response = _api_client(self.admin).patch(
            "/api/v1/tenants/me/feature-flags/",
            {"databricks_sso_enabled": True},
            format="json",
        )
        assert response.status_code == 200, response.content

        self.tenant.refresh_from_db()
        assert self.tenant.databricks_sso_enabled is True

        event = (
            AuditEvent.objects.filter(action="TENANT_FEATURE_FLAG_UPDATED")
            .order_by("-timestamp")
            .first()
        )
        assert event is not None, "a flag flip must emit a real audit row"
        details = event.details_json or {}
        assert details.get("flag_name") == "databricks_sso_enabled"
        assert details.get("previous_value") is False
        assert details.get("new_value") is True


class JobsPythonTasksFlagTests(TestCase):
    """4.3 — the `databricks_jobs_python_tasks_enabled` flag (the D3
    Python-task gate): registered DRAFT default-off, tenant field
    default False (the jobs client refuses Python tasks until flipped)."""

    def test_jobs_python_flag_registered_as_draft_default_off(self):
        flag = feature_flag_registry.get_flag("databricks_jobs_python_tasks_enabled")
        assert flag is not None, "flag must be registered in the lifecycle registry"
        assert flag.stage == "DRAFT"
        assert flag.default_new_tenants is False
        assert flag.default_existing_tenants is False

    def test_jobs_python_flag_tenant_field_defaults_false(self):
        tenant = TenantFactory.create_tenant()
        tenant.refresh_from_db()
        assert tenant.databricks_jobs_python_tasks_enabled is False
