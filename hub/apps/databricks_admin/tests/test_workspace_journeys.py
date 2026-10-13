"""JOURNEY-DB-001 / JOURNEY-DB-002 backend journey tests (task 0.17).

The class/method names here are PINNED by the canonical use-case docs
(``docs/mvpdocs/use-cases/UC-DB-001.md`` / ``UC-DB-002.md`` "Phase P0
Test" fields) — renaming them requires updating those docs in the same PR
(GATE-28 checks the bidirectional sync).

No mocks: real Postgres, real RBAC (TENANT_ADMIN), real Fernet encryption,
and the probe/rotation actions drive the PRODUCTION Databricks client
against a REAL local HTTP server — the only seam is the view's
``_build_probe_client`` factory (the repo's own pattern, shared with
test_views.py / test_credential_endpoints.py).
"""

import json
import uuid

import pytest
from django.db import connection

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
from hub.apps.databricks_admin.tests.test_views import (
    WORKSPACES_URL,
    _api_client,
    _new_tenant_with_admin,
    _workspace_with_credential,
)

pytestmark = pytest.mark.django_db(transaction=True)


def _credentials_url(workspace_id, credential_id=None):
    base = f"/api/v1/databricks/workspaces/{workspace_id}/credentials/"
    if credential_id:
        return f"{base}{credential_id}/rotate/"
    return base


def _patch_probe_transport(monkeypatch, port):
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


def _raw_config_column(credential) -> str:
    with connection.cursor() as cursor:
        cursor.execute("SELECT config FROM databricks_credentials WHERE id = %s", [credential.id])
        row = cursor.fetchone()
    assert row is not None
    return row[0]


@pytest.mark.journey("JOURNEY-DB-001")
@pytest.mark.uc("UC-DB-001")
class TestJOURNEYDB001RegisterWorkspace:
    """Register a Databricks Workspace — the full guided path:
    register → attach credential → test → ACTIVE."""

    def _setup(self):
        require_dns()
        tenant, admin = _new_tenant_with_admin(f"db001-{uuid.uuid4().hex[:8]}@test.com")
        return tenant, admin

    def test_register_workspace_success(self, monkeypatch, local_http_server):
        """The pinned P0 test: a registered workspace survives the whole
        journey — REAL row, REAL encrypted credential, REAL probe against
        the local transport, ACTIVE status, and the two audit events."""
        from hub.apps.audit.models import AuditEvent

        _tenant, admin = self._setup()
        unique = uuid.uuid4().hex[:8]
        response = _api_client(admin).post(
            WORKSPACES_URL,
            {
                "name": f"journey-{unique}",
                "host": REAL_HOST,
                "cloud": DatabricksCloud.AWS,
                "region": "us-east-1",
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        workspace_id = response.json()["id"]

        workspace = DatabricksWorkspace.objects.get(id=workspace_id)
        assert workspace.status == DatabricksWorkspaceStatus.REGISTERED
        assert workspace.host == REAL_HOST

        # Attach a PAT credential (real encryption at rest).
        cred_response = _api_client(admin).post(
            _credentials_url(workspace_id),
            {"auth_mode": "PAT", "config": {"token": f"dapi-journey-{unique}"}},
            format="json",
        )
        assert cred_response.status_code == 201, cred_response.content
        assert "config" not in cred_response.json()

        credential = DatabricksCredential.objects.get(id=cred_response.json()["id"])
        raw = _raw_config_column(credential)
        assert "dapi-journey" not in (raw if isinstance(raw, str) else json.dumps(raw))

        # Probe → ACTIVE (real client against the local HTTP transport).
        RecordingHandler.script = [200]
        _patch_probe_transport(monkeypatch, local_http_server)
        test_response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace_id}/test/")
        assert test_response.status_code == 200, test_response.content
        assert test_response.json()["status"] == "ok"

        workspace.refresh_from_db()
        assert workspace.status == DatabricksWorkspaceStatus.ACTIVE

        # Both journey audit events landed, without credential material.
        registered = AuditEvent.objects.filter(
            action="REGISTERED", resource_id=workspace.id
        ).first()
        assert registered is not None
        passed = AuditEvent.objects.filter(action="TEST_PASSED", resource_id=workspace.id).first()
        assert passed is not None
        for event in (registered, passed):
            assert "dapi" not in json.dumps(event.details_json or {})


@pytest.mark.journey("JOURNEY-DB-002")
@pytest.mark.uc("UC-DB-002")
class TestJOURNEYDB002TestConnectionRotateCredentials:
    """Test Workspace Connection and Rotate Credentials."""

    def _setup(self):
        require_dns()
        tenant, admin = _new_tenant_with_admin(f"db002-{uuid.uuid4().hex[:8]}@test.com")
        workspace = _workspace_with_credential(tenant)
        return tenant, admin, workspace

    def test_connection_returns_active_with_latency(self, monkeypatch, local_http_server):
        _tenant, admin, workspace = self._setup()
        RecordingHandler.script = [200]
        _patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(f"{WORKSPACES_URL}{workspace.id}/test/")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert isinstance(body.get("latency_ms"), (int, float))

        workspace.refresh_from_db()
        assert workspace.status == DatabricksWorkspaceStatus.ACTIVE

    def test_rotate_pat_rewrites_ciphertext_and_audits(self, monkeypatch, local_http_server):
        """The pinned P0 test: PAT rotation replaces the token on the
        Databricks side (create-PAT + delete-old against the REAL local
        transport), rewrites the ciphertext, stamps last_rotated_at, and
        writes the ROTATED audit row without credential material."""
        from hub.apps.audit.models import AuditEvent

        _tenant, admin, workspace = self._setup()
        credential = workspace.credentials.first()
        old_raw = _raw_config_column(credential)
        old_config = credential.get_config()

        RecordingHandler.json_script = [
            '{"token_value": "dapi-journey-new", "token_info": {"token_id": "new-token-id"}}',
        ]
        _patch_probe_transport(monkeypatch, local_http_server)

        response = _api_client(admin).post(_credentials_url(workspace.id, credential.id))
        assert response.status_code == 200, response.content
        assert "config" not in response.json()

        credential.refresh_from_db()
        new_raw = _raw_config_column(credential)
        assert new_raw != old_raw, "rotation must rewrite the ciphertext"
        assert credential.get_config().get("token") == "dapi-journey-new"
        assert credential.get_config().get("token_id") == "new-token-id"
        assert credential.last_rotated_at is not None

        # The old PAT's deletion was requested against the transport.
        assert RecordingHandler.requests, "rotation must call the transport"

        event = AuditEvent.objects.filter(action="ROTATED").order_by("-timestamp").first()
        assert event is not None, "rotation must emit a real audit row"
        assert event.resource_type == "DATABRICKS_CREDENTIAL"
        serialized = json.dumps(event.details_json or {})
        assert "dapi" not in serialized
        assert str(old_config) not in serialized

    def test_rotate_m2m_requires_client_secret(self):
        _tenant, admin, workspace = self._setup()
        m2m = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            config={"client_id": "cid-1", "client_secret": "sec-1"},
        )
        response = _api_client(admin).post(_credentials_url(workspace.id, m2m.id))
        assert response.status_code == 400
        assert response.json()["code"] == "DATABRICKS_CLIENT_SECRET_REQUIRED"
