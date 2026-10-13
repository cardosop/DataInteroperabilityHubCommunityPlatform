"""P0 (openspec add-databricks-control-plane task 0.9) — credential endpoints.

No mocks: real Postgres, real RBAC, the REAL encryption chain (Fernet), and
the rotation action drives the PRODUCTION client against a REAL local HTTP
server through the view's client factory (same seam as the probe action).
Assertions include the raw stored column (no plaintext) and the real
audit rows.
"""

import json
import uuid

import pytest
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.databricks_admin import views as admin_views
from hub.apps.databricks_admin.client import DatabricksApiClient
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksWorkspace,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.users.models import Role, User, UserRole
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


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
    user = User.objects.create_user(email=email, password="testpass123", tenant=tenant)
    if role_name:
        role, _ = Role.objects.get_or_create(tenant=tenant, name=role_name)
        UserRole.objects.get_or_create(user=user, role=role)
    return user


def _api_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _credentials_url(workspace_id, credential_id=None):
    base = f"/api/v1/databricks/workspaces/{workspace_id}/credentials/"
    if credential_id:
        return f"{base}{credential_id}/rotate/"
    return base


class CredentialEndpointTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.admin = _make_user(self.tenant, "cred-admin@test.com", "TENANT_ADMIN")
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )

    def _raw_config_column(self, credential) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT config FROM databricks_credentials WHERE id = %s", [credential.id]
            )
            row = cursor.fetchone()
        assert row is not None
        return row[0]

    # ── create ────────────────────────────────────────────────────────────

    def test_create_emits_stored_audit_event_with_no_credential_material(self):
        """0.16 — credential create writes a REAL ``STORED`` audit row and
        never leaks credential material into the audit payload."""
        from hub.apps.audit.models import AuditEvent

        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": {"token": "dapi-store-secret"}},
            format="json",
        )
        assert response.status_code == 201, response.content

        event = AuditEvent.objects.filter(action="STORED").order_by("-timestamp").first()
        assert event is not None, "credential storage must emit a real audit row"
        assert event.resource_type == "DATABRICKS_CREDENTIAL"
        assert event.tenant_id == self.tenant.id
        serialized = json.dumps(event.details_json or {})
        assert "dapi" not in serialized, "no token material in audit details"
        assert "secret" not in serialized.lower(), "no secret material in audit details"

    def test_create_encrypts_at_rest_and_redacts_response(self):
        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": {"token": "dapi-create-secret"}},
            format="json",
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert "config" not in body, "config must never be returned"

        credential = DatabricksCredential.objects.get(id=body["id"])
        raw = self._raw_config_column(credential)
        raw_text = raw if isinstance(raw, str) else json.dumps(raw)
        assert "_encrypted" in raw_text
        assert "dapi-create-secret" not in raw_text
        assert credential.get_config() == {"token": "dapi-create-secret"}

    def test_list_returns_metadata_only(self):
        DatabricksCredential.objects.create(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-list-secret"},
        )
        response = _api_client(self.admin).get(_credentials_url(self.workspace.id))
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list), "nested credential list is unpaginated"
        for item in body:
            assert "config" not in item

    def test_create_requires_tenant_admin(self):
        viewer = _make_user(self.tenant, "cred-viewer@test.com")
        response = _api_client(viewer).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": {"token": "dapi-x"}},
            format="json",
        )
        assert response.status_code == 403

    def test_cross_tenant_workspace_path_is_404(self):
        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_admin = _make_user(other_tenant, "cred-other@test.com", "TENANT_ADMIN")
        response = _api_client(other_admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": {"token": "dapi-x"}},
            format="json",
        )
        assert response.status_code == 404

    def test_throttle_scope_enforced_after_burst(self):
        # Real DRF throttle: 30/minute per scope — the 31st request must 429.
        # A FRESH user keeps the throttle cache isolated from other tests.
        throttled_admin = _make_user(self.tenant, "cred-throttle-admin@test.com", "TENANT_ADMIN")
        client = _api_client(throttled_admin)
        for _ in range(30):
            assert client.get(_credentials_url(self.workspace.id)).status_code == 200
        assert client.get(_credentials_url(self.workspace.id)).status_code == 429

    def test_create_rejects_non_dict_config(self):
        # A bare JSON string/array would be stored in PLAINTEXT by the model
        # (the wrapper-shape guard only encrypts dicts) — the API must
        # reject it so encryption-at-rest cannot be bypassed.
        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": "dapi-plaintext-string"},
            format="json",
        )
        assert response.status_code == 400
        assert not DatabricksCredential.objects.filter(workspace=self.workspace).exists(), (
            "a non-dict config must never reach the database"
        )

    def test_create_pat_requires_token(self):
        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "PAT", "config": {"comment": "no token here"}},
            format="json",
        )
        assert response.status_code == 400
        assert not DatabricksCredential.objects.filter(workspace=self.workspace).exists()

    def test_create_m2m_requires_client_id_and_secret(self):
        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {"auth_mode": "OAUTH_M2M", "config": {"client_id": "cid-1"}},
            format="json",
        )
        assert response.status_code == 400
        assert not DatabricksCredential.objects.filter(workspace=self.workspace).exists()

    def test_create_m2m_succeeds_with_full_config(self):
        response = _api_client(self.admin).post(
            _credentials_url(self.workspace.id),
            {
                "auth_mode": "OAUTH_M2M",
                "config": {"client_id": "cid-1", "client_secret": "sec-1"},
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        assert "config" not in response.json(), "config must never be returned"


class TestCredentialRotation:
    """Rotation tests — pytest-fixture-driven (TestCase methods cannot
    take fixtures), same real infrastructure."""

    def _setup(self):
        require_dns()
        tenant = TenantFactory.create_tenant()
        _activate_billing(tenant)
        admin = _make_user(tenant, "rotate-admin@test.com", "TENANT_ADMIN")
        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name="prod",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        return tenant, admin, workspace

    def _patch_client_factory(self, monkeypatch, port):
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

        monkeypatch.setattr(admin_views, "_build_probe_client", fake_factory)

    def _credential(self, workspace, config=None):
        return DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config=config or {"token": "dapi-old-token"},
        )

    def test_rotate_pat_creates_replacement_and_rewrites_ciphertext(
        self, monkeypatch, local_http_server
    ):
        _tenant, admin, workspace = self._setup()
        credential = self._credential(workspace)
        RecordingHandler.json_script = [
            '{"token_value": "dapi-new-token", "token_info": {"token_id": "new-token-id"}}',
        ]
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 200, response.content

        credential.refresh_from_db()
        assert credential.get_config().get("token") == "dapi-new-token"
        assert credential.get_config().get("token_id") == "new-token-id"
        assert credential.last_rotated_at is not None

        raw = self._raw_config(credential)
        assert "dapi-new-token" not in raw, "new token must be stored encrypted"

        create_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"] == "/api/2.0/token-management/on-behalf-of/tokens"
        ]
        assert len(create_calls) == 1

    def test_rotate_pat_deletes_previous_token_when_id_known(self, monkeypatch, local_http_server):
        _tenant, admin, workspace = self._setup()
        credential = self._credential(
            workspace, config={"token": "dapi-old-token", "token_id": "old-token-id"}
        )
        RecordingHandler.json_script = [
            '{"token_value": "dapi-new-token", "token_info": {"token_id": "new-token-id"}}',
            "{}",
        ]
        RecordingHandler.script = [200, 200]
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 200

        delete_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"] == "/api/2.0/token-management/tokens/old-token-id"
        ]
        assert len(delete_calls) == 1, (
            "the previous token id must be deleted on the Databricks side"
        )

    def test_rotate_m2m_rewrites_secret_without_api_calls(self, monkeypatch, local_http_server):
        _tenant, admin, workspace = self._setup()
        credential = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-1", "client_secret": "old-secret"},
        )
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(
            _credentials_url(workspace.id, credential.id),
            {"client_secret": "new-secret-value"},
            format="json",
        )
        assert response.status_code == 200, response.content

        credential.refresh_from_db()
        assert credential.get_config() == {
            "client_id": "cid-1",
            "client_secret": "new-secret-value",
        }
        assert RecordingHandler.requests == [], "M2M re-issue must not call the Databricks API"

    def test_rotate_failure_leaves_config_untouched(self, monkeypatch, local_http_server):
        _tenant, admin, workspace = self._setup()
        credential = self._credential(workspace)
        RecordingHandler.script = [401]
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 502
        assert response.json()["code"] == "DATABRICKS_AUTH_FAILED"

        credential.refresh_from_db()
        assert credential.get_config() == {"token": "dapi-old-token"}, (
            "failed rotation must be atomic"
        )

    def test_rotate_emits_audit_event(self, monkeypatch, local_http_server):
        from hub.apps.audit.models import AuditEvent

        _tenant, admin, workspace = self._setup()
        credential = self._credential(workspace)
        RecordingHandler.json_script = [
            '{"token_value": "dapi-new-token", "token_info": {"token_id": "new-token-id"}}',
        ]
        self._patch_client_factory(monkeypatch, local_http_server)

        _api_client(admin).post(_credentials_url(workspace.id, credential.id))

        event = AuditEvent.objects.filter(action="ROTATED").order_by("-timestamp").first()
        assert event is not None, "rotation must emit a real audit row"
        assert event.resource_type == "DATABRICKS_CREDENTIAL"
        assert "dapi" not in json.dumps(event.details_json or {}), (
            "no token material in audit details"
        )

    def test_rotate_delete_old_failure_cleans_up_replacement_token(
        self, monkeypatch, local_http_server
    ):
        # Rotation failure AFTER the replacement token was created must not
        # leave a live, unrecorded token at Databricks: the just-created
        # token id must be deleted best-effort before returning 502.
        _tenant, admin, workspace = self._setup()
        credential = self._credential(
            workspace, config={"token": "dapi-old-token", "token_id": "old-token-id"}
        )
        RecordingHandler.json_script = [
            '{"token_value": "dapi-new-token", "token_info": {"token_id": "new-token-id"}}',
            "{}",
            "{}",
        ]
        RecordingHandler.script = [200, 401, 200]  # create OK, delete-old fails, cleanup OK
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 502

        old_delete_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"] == "/api/2.0/token-management/tokens/old-token-id"
        ]
        new_delete_calls = [
            r
            for r in RecordingHandler.requests
            if r["path"] == "/api/2.0/token-management/tokens/new-token-id"
        ]
        assert len(old_delete_calls) == 1
        assert len(new_delete_calls) == 1, (
            "the replacement token created moments before the failure must be deleted"
        )

        credential.refresh_from_db()
        assert credential.get_config() == {"token": "dapi-old-token", "token_id": "old-token-id"}, (
            "failed rotation must be atomic"
        )

    def test_rotate_m2m_without_secret_is_400(self, monkeypatch, local_http_server):
        _tenant, admin, workspace = self._setup()
        credential = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-1", "client_secret": "old-secret"},
        )
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(
            _credentials_url(workspace.id, credential.id), {}, format="json"
        )
        assert response.status_code == 400
        assert response.json()["code"] == "DATABRICKS_CLIENT_SECRET_REQUIRED"
        assert RecordingHandler.requests == [], "missing-secret rejection must not call the API"

    def test_rotate_cross_tenant_workspace_is_404(self, monkeypatch, local_http_server):
        _tenant, _admin, workspace = self._setup()
        credential = self._credential(workspace)

        other_tenant = TenantFactory.create_tenant()
        _activate_billing(other_tenant)
        other_admin = _make_user(other_tenant, "rotate-other@test.com", "TENANT_ADMIN")
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(other_admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 404

    def test_rotate_non_object_response_is_masked_502(self, monkeypatch, local_http_server):
        # A 2xx body that is not a JSON object (e.g. an array) must surface
        # as a masked 502 with the stored config untouched — never a raw
        # AttributeError from `.get()` on a list.
        _tenant, admin, workspace = self._setup()
        credential = self._credential(workspace)
        RecordingHandler.json_script = ["[1, 2, 3]"]
        self._patch_client_factory(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 502
        assert response.json()["code"] == "DATABRICKS_AUTH_FAILED"

        credential.refresh_from_db()
        assert credential.get_config() == {"token": "dapi-old-token"}, (
            "unparseable rotation responses must be atomic"
        )

    @staticmethod
    def _raw_config(credential) -> str:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT config FROM databricks_credentials WHERE id = %s",
                [credential.id],
            )
            row = cursor.fetchone()
        assert row is not None
        raw = row[0]
        return raw if isinstance(raw, str) else json.dumps(raw)
