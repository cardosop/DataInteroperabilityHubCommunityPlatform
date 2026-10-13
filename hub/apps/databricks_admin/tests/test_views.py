"""P0 (openspec add-databricks-control-plane task 0.8) — Workspace ViewSet.

No mocks: real Postgres, real RBAC (TENANT_ADMIN role), real encrypted
credential rows, and the test-probe action drives the PRODUCTION client
against a REAL local HTTP server — the only seam is the view's
``_build_probe_client`` factory, redirected to the local transport (the
repo's own pattern for view-level network actions: warehouses tests patch
the connector factory the same way).
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin import views as workspace_views
from hub.apps.databricks_admin.client import DatabricksApiClient
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
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
    tenant.databricks_control_plane_enabled = True
    tenant.save(update_fields=["databricks_control_plane_enabled"])


def _make_user(tenant, email, role_name=None):
    email = f"{uuid.uuid4().hex[:8]}-{email}"
    user = User.objects.create_user(
        email=email,
        password="testpass123",
        tenant=tenant,
    )
    if role_name:
        role, _ = Role.objects.get_or_create(tenant=tenant, name=role_name)
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _payload(**overrides):
    payload = {
        "name": "prod",
        "host": REAL_HOST,
        "cloud": DatabricksCloud.AWS,
        "region": "us-east-1",
    }
    payload.update(overrides)
    return payload


def _new_tenant_with_admin(admin_email):
    require_dns()
    tenant = TenantFactory.create_tenant()
    _activate_billing(tenant)
    admin = _make_user(tenant, admin_email, "TENANT_ADMIN")
    return tenant, admin


def _workspace_with_credential(tenant):
    workspace = DatabricksWorkspace.objects.create(
        tenant=tenant,
        name="prod",
        host=REAL_HOST,
        cloud=DatabricksCloud.AWS,
        region="us-east-1",
    )
    DatabricksCredential.objects.create(
        workspace=workspace,
        auth_mode=DatabricksCredentialAuthMode.PAT,
        config={"token": "dapi-secret-token"},
    )
    return workspace


class WorkspaceViewSetTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant_a = TenantFactory.create_tenant()
        self.tenant_b = TenantFactory.create_tenant()
        _activate_billing(self.tenant_a)
        _activate_billing(self.tenant_b)
        self.admin_a = _make_user(self.tenant_a, "admin-a@test.com", "TENANT_ADMIN")
        self.admin_b = _make_user(self.tenant_b, "admin-b@test.com", "TENANT_ADMIN")
        self.viewer_a = _make_user(self.tenant_a, "viewer-a@test.com")

    def _create_workspace(self):
        response = _api_client(self.admin_a).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 201, response.content
        return response

    # ── RBAC + tenant scoping ────────────────────────────────────────────

    def test_create_requires_tenant_admin_role(self):
        response = _api_client(self.viewer_a).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 403

    def test_create_and_list_are_tenant_scoped(self):
        self._create_workspace()
        listed = _api_client(self.admin_a).get(WORKSPACES_URL)
        assert listed.status_code == 200
        body = listed.json()
        assert body["count"] == 1
        assert len(body["results"]) == 1

        other_list = _api_client(self.admin_b).get(WORKSPACES_URL)
        assert other_list.status_code == 200
        assert other_list.json()["results"] == [], "tenant B must not see tenant A workspaces"

    def test_detail_cross_tenant_is_404(self):
        created = self._create_workspace()
        workspace_id = created.json()["id"]
        response = _api_client(self.admin_b).get(f"{WORKSPACES_URL}{workspace_id}/")
        assert response.status_code == 404

    # ── host validation envelope ──────────────────────────────────────────

    def test_invalid_host_envelope_carries_domain_code_and_human_message(self):
        """Envelope contract (task 0.15): a family-invalid host must answer
        with the machine-readable ``DATABRICKS_HOST_NOT_ALLOWED`` code — not
        the generic ``VALIDATION_ERROR`` — and a HUMAN message (never the
        DRF ``ErrorDetail`` Python repr)."""
        response = _api_client(self.admin_a).post(
            WORKSPACES_URL,
            _payload(name="bad-host", host="attacker.example.com"),
            format="json",
        )
        assert response.status_code == 400
        body = response.json()
        assert body["error"]["code"] == "DATABRICKS_HOST_NOT_ALLOWED"
        assert "attacker.example.com" in body["error"]["message"]
        assert "ErrorDetail" not in body["error"]["message"]

    # ── delete / soft-delete ──────────────────────────────────────────────

    def test_delete_with_dependents_is_409(self):
        workspace = _workspace_with_credential(self.tenant_a)
        response = _api_client(self.admin_a).delete(f"{WORKSPACES_URL}{workspace.id}/")
        assert response.status_code == 409
        body = response.json()
        assert body["code"] == "DATABRICKS_WORKSPACE_HAS_DEPENDENTS"
        assert str(workspace.credentials.first().id) in str(body["dependent_object_ids"])

    def test_duplicate_name_same_tenant_is_400(self):
        self._create_workspace()
        # Same tenant + same name violates the (tenant, name) unique
        # constraint — must surface as a clean 400, never a raw 500.
        response = _api_client(self.admin_a).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 400
        assert response.json()["code"] == "DATABRICKS_WORKSPACE_NAME_CONFLICT"

    def test_duplicate_name_other_tenant_is_allowed(self):
        self._create_workspace()
        response = _api_client(self.admin_b).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 201, "same name in another tenant is legal"

    def test_throttle_scope_enforced_after_burst(self):
        # Real DRF throttle: 30/minute per scope — the 31st request must 429.
        # A FRESH user keeps the throttle cache isolated from other tests.
        throttled_admin = _make_user(self.tenant_a, "throttle-admin@test.com", "TENANT_ADMIN")
        client = _api_client(throttled_admin)
        for _ in range(30):
            assert client.get(WORKSPACES_URL).status_code == 200
        assert client.get(WORKSPACES_URL).status_code == 429

    def test_delete_without_dependents_soft_disables(self):
        workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant_a,
            name="disposable",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        response = _api_client(self.admin_a).delete(f"{WORKSPACES_URL}{workspace.id}/")
        assert response.status_code == 204

        workspace.refresh_from_db()
        assert workspace.status == DatabricksWorkspaceStatus.DISABLED, "delete is a soft-disable"


class TestWorkspaceAuditEvents(TestCase):
    """0.16 — workspace lifecycle writes REAL audit rows (no mocks)."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(
            self.tenant, f"audit-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )

    def _audit_rows(self, action):
        from hub.apps.audit.models import AuditEvent

        return AuditEvent.objects.filter(
            action=action, resource_type="DATABRICKS_WORKSPACE"
        ).order_by("-timestamp")

    def test_audit_pins_ignore_foreign_rows_with_same_action(self):
        # The shared test DB accumulates leaked rows from parallel sessions;
        # a foreign row (another app) with the SAME action and a later
        # timestamp must never satisfy the databricks pin.
        from hub.apps.audit.models import AuditEvent

        AuditEvent.objects.create(
            tenant=self.tenant,
            resource_type="OTHER_APP",
            action="REGISTERED",
            result="SUCCESS",
        )
        response = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 201, response.content

        row = self._audit_rows("REGISTERED").first()
        assert row is not None, "registration must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"

    def test_create_emits_registered_row(self):
        response = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        assert response.status_code == 201, response.content

        row = self._audit_rows("REGISTERED").first()
        assert row is not None, "registration must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert row.tenant_id == self.tenant.id
        assert str(row.resource_id) == response.json()["id"]
        assert row.result == "SUCCESS"

    def test_update_emits_updated_row(self):
        created = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        ws_id = created.json()["id"]
        response = _api_client(self.admin).patch(
            f"{WORKSPACES_URL}{ws_id}/", {"name": "renamed"}, format="json"
        )
        assert response.status_code == 200, response.content

        row = self._audit_rows("UPDATED").first()
        assert row is not None, "update must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert str(row.resource_id) == ws_id

    def test_delete_emits_deleted_row(self):
        created = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        ws_id = created.json()["id"]
        response = _api_client(self.admin).delete(f"{WORKSPACES_URL}{ws_id}/")
        assert response.status_code in (200, 204), response.content

        row = self._audit_rows("DELETED").first()
        assert row is not None, "delete must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert str(row.resource_id) == ws_id

    def test_test_without_credential_emits_failed_row(self):
        created = _api_client(self.admin).post(WORKSPACES_URL, _payload(), format="json")
        ws_id = created.json()["id"]
        response = _api_client(self.admin).post(f"{WORKSPACES_URL}{ws_id}/test/")
        assert response.status_code == 502

        row = self._audit_rows("TEST_FAILED").first()
        assert row is not None, "masked probe failure must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert row.result == "FAILURE"


class TestWorkspaceProbe:
    """Probe-action tests — pytest-fixture-driven (TestCase methods cannot
    take fixtures), same real infrastructure."""

    def _patch_probe_transport(self, monkeypatch, port):
        def fake_factory(workspace, credential):
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(workspace.tenant_id),
                credential_config=credential.get_config(),
                auth_mode=credential.auth_mode,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        monkeypatch.setattr(workspace_views, "_build_probe_client", fake_factory)

    def test_test_action_success_transitions_to_active(self, monkeypatch, local_http_server):
        tenant, admin = _new_tenant_with_admin("probe-ok@test.com")
        workspace = _workspace_with_credential(tenant)
        RecordingHandler.script = [200]
        self._patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace.id}/test/")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        workspace.refresh_from_db()
        assert workspace.status == DatabricksWorkspaceStatus.ACTIVE

    def test_test_action_failure_is_masked_502(self, monkeypatch, local_http_server):
        tenant, admin = _new_tenant_with_admin("probe-fail@test.com")
        workspace = _workspace_with_credential(tenant)
        RecordingHandler.script = [401]
        self._patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace.id}/test/")
        assert response.status_code == 502
        body = response.json()
        assert body["code"] == "DATABRICKS_AUTH_FAILED"
        assert body["message"] == "Credentials rejected by workspace"
        assert "dapi-secret-token" not in response.content.decode(), "token must never leak"

        workspace.refresh_from_db()
        assert workspace.status == DatabricksWorkspaceStatus.REGISTERED, (
            "failure must not mutate state"
        )

    def test_test_action_success_emits_test_passed_audit_row(self, monkeypatch, local_http_server):
        from hub.apps.audit.models import AuditEvent

        tenant, admin = _new_tenant_with_admin("probe-audit-ok@test.com")
        workspace = _workspace_with_credential(tenant)
        RecordingHandler.script = [200]
        self._patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace.id}/test/")
        assert response.status_code == 200

        row = AuditEvent.objects.filter(action="TEST_PASSED").order_by("-timestamp").first()
        assert row is not None, "successful probe must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert str(row.resource_id) == str(workspace.id)
        assert row.result == "SUCCESS"
        assert "latency_ms" in (row.details_json or {})

    def test_test_action_failure_emits_test_failed_audit_row(self, monkeypatch, local_http_server):
        from hub.apps.audit.models import AuditEvent

        tenant, admin = _new_tenant_with_admin("probe-audit-fail@test.com")
        workspace = _workspace_with_credential(tenant)
        RecordingHandler.script = [401]
        self._patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace.id}/test/")
        assert response.status_code == 502

        row = AuditEvent.objects.filter(action="TEST_FAILED").order_by("-timestamp").first()
        assert row is not None, "failed probe must emit a real audit row"
        assert row.resource_type == "DATABRICKS_WORKSPACE"
        assert row.result == "FAILURE"
