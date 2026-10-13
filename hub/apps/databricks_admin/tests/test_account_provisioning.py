"""P8 (openspec add-databricks-account-plane task 8.3, design D3/D4) — the
provisioning surface battery.

Metastore ops + workspace provisioning through the REAL account API —
refused with HTTP 403 and ZERO network unless BOTH the target tenant's
``databricks_workspace_provisioning_enabled`` flag is ON and a COMPLETE
DPO/Legal signoff is recorded on the account row (the D3 triple; the
signoff check runs FIRST — the legal prerequisite). A provisioned
workspace attaches to the tenant through the EXISTING registry validation
(host SSRF + region residency — never bypassed). The surface is
PLATFORM_ADMIN-only (a non-platform caller gets 403 PERMISSION_DENIED).

No mocks: real Postgres rows (account via the forced admin alias, target
tenant, signoff user, workspace registry row), the PRODUCTION
``DatabricksAccountClient`` over a REAL threaded local account-API server,
and the REAL DRF views over real HTTP with ``force_authenticate``. The
sanctioned seam is the service's default-client-factory symbol (the 7.4
``_do_query`` recorder convention) — the refusal pins record ZERO factory
invocations so a broken gate could never reach the REAL account host.
"""

import uuid

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

TOKEN = "dapi-account-token"


@pytest.fixture
def local_account_server():
    """A real local HTTP server on an ephemeral port (no mocks)."""
    import http.server
    import threading

    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _platform_user():
    from hub.apps.users.models import User, UserStatus

    user = User.objects.create_user(
        email=f"acct-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        status=UserStatus.ACTIVE,
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _account():
    from hub.apps.databricks_admin.models import DatabricksAccount

    account = DatabricksAccount(
        account_id=uuid.uuid4(),
        display_name=f"acct-{uuid.uuid4().hex[:8]}",
    )
    account.set_config({"token": TOKEN})
    account.save()
    return account


def _signoff(account):
    from hub.apps.users.models import User, UserStatus

    signer = User.objects.create_user(
        email=f"dpo-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        status=UserStatus.ACTIVE,
    )
    account.record_provisioning_signoff(
        signer, "https://governance.meshant.test/databricks-provisioning/signoff-42"
    )
    return signer


def _enable_flag(tenant):
    tenant.databricks_workspace_provisioning_enabled = True
    tenant.save(update_fields=["databricks_workspace_provisioning_enabled"])
    return tenant


def _patch_default_factory(monkeypatch, port):
    """Point the service's default client factory at the LOCAL account-API
    server AND record every invocation (the sanctioned seam — the refusal
    pins assert ZERO invocations so a broken gate can never reach the
    real account host)."""
    from hub.apps.databricks_admin.account_client import DatabricksAccountClient

    calls = []

    def factory(account):
        calls.append(account)
        return DatabricksAccountClient(
            str(account.account_id),
            account.get_config(),
            base_url=f"http://127.0.0.1:{port}",
            retry_base_delay=0.01,
            retry_max_delay=0.02,
        )

    from hub.apps.databricks_admin import account_ops

    monkeypatch.setattr(account_ops, "_default_client_factory", factory)
    return calls


class TestRefusals:
    def test_flag_off_refuses_with_zero_network(self, monkeypatch, local_account_server):
        from rest_framework import status as http

        tenant = TenantFactory.create_tenant()  # flag default-off
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_account_server)

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_403_FORBIDDEN
        assert resp.json()["error"]["code"] == "DATABRICKS_WORKSPACE_PROVISIONING_DISABLED"
        assert calls == [], "no client build — ZERO network for a refused provisioning"
        assert RecordingHandler.requests == []

    def test_signoff_missing_refuses_with_zero_network(self, monkeypatch, local_account_server):
        from rest_framework import status as http

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()  # no signoff
        calls = _patch_default_factory(monkeypatch, local_account_server)

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_403_FORBIDDEN
        assert resp.json()["error"]["code"] == "DATABRICKS_PROVISIONING_SIGNOFF_MISSING"
        assert calls == [], "no client build — ZERO network for a refused provisioning"
        assert RecordingHandler.requests == []

    def test_metastore_create_shares_the_same_gate(self, monkeypatch, local_account_server):
        from rest_framework import status as http

        tenant = TenantFactory.create_tenant()  # flag off
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_account_server)

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/metastores/",
            {"tenant_id": str(tenant.id), "name": "meshant-shared", "region": "us-east-1"},
            format="json",
        )

        assert resp.status_code == http.HTTP_403_FORBIDDEN
        assert resp.json()["error"]["code"] == "DATABRICKS_WORKSPACE_PROVISIONING_DISABLED"
        assert calls == [], "the uniform gate refuses every provisioning request"
        assert RecordingHandler.requests == []

    def test_non_platform_admin_is_refused(self, monkeypatch, local_account_server):
        from rest_framework import status as http

        from hub.apps.users.models import User, UserStatus

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_account_server)
        bystander = User.objects.create_user(
            email=f"bystander-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            status=UserStatus.ACTIVE,
        )

        resp = _client(bystander).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_403_FORBIDDEN
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"
        assert calls == [], "RBAC refuses before any provisioning logic"
        assert RecordingHandler.requests == []

    def test_unauthenticated_requests_get_401(self, monkeypatch, local_account_server):
        # DRF's permission_denied contract: an ANONYMOUS caller gets 401
        # NotAuthenticated — never the 403 PERMISSION_DENIED the RBAC gate
        # reserves for authenticated non-platform callers (8.4 review fix;
        # the unconditional override sent anonymous callers 403).
        from rest_framework import status as http

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_account_server)

        resp = APIClient().post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_401_UNAUTHORIZED
        assert calls == [], "401 refuses before any provisioning logic"
        assert RecordingHandler.requests == []

    def test_missing_required_fields_refuse_before_any_network(
        self, monkeypatch, local_account_server
    ):
        from rest_framework import status as http

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_account_server)
        client = _client(_platform_user())

        missing_tenant = client.post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {"workspace_name": "meshant-ws", "aws_region": "us-east-1"},
            format="json",
        )
        assert missing_tenant.status_code == http.HTTP_400_BAD_REQUEST
        missing_region = client.post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {"tenant_id": str(tenant.id), "workspace_name": "meshant-ws"},
            format="json",
        )
        assert missing_region.status_code == http.HTTP_400_BAD_REQUEST
        assert calls == [], "shape discipline refuses before any client build"
        assert RecordingHandler.requests == []


class TestProvisioningHappyPath:
    def test_provision_workspace_attaches_the_registry_row(self, monkeypatch, local_account_server):
        require_dns()
        from rest_framework import status as http

        from hub.apps.databricks_admin.models import DatabricksWorkspace

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        _patch_default_factory(monkeypatch, local_account_server)
        RecordingHandler.json_script = [
            '{"workspace_id": 7000000000000001, "workspace_name": "meshant-ws", '
            f'"deployment_name": "dbc-8fe1", "workspace_url": "https://{REAL_HOST}", '
            '"workspace_status": "PROVISIONING"}',
        ]

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
                "pricing_tier": "ENTERPRISE",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_201_CREATED, resp.content
        body = resp.json()
        assert body["tenant_id"] == str(tenant.id)
        assert body["host"] == REAL_HOST
        assert body["status"] == "REGISTERED"

        row = DatabricksWorkspace.objects.get(tenant=tenant)
        assert row.host == REAL_HOST, "the registry row carries the provisioned host"
        assert row.cloud == "AWS"
        assert row.region == "us-east-1"
        assert row.name == "meshant-ws"

        recorded = RecordingHandler.requests
        assert len(recorded) == 1
        request = recorded[0]
        assert request["method"] == "POST"
        assert request["path"] == f"/api/2.0/accounts/{account.account_id}/workspaces"
        import json

        sent = json.loads(request["body"])
        assert sent["workspace_name"] == "meshant-ws"
        assert sent["aws_region"] == "us-east-1"
        assert sent["pricing_tier"] == "ENTERPRISE"

    def test_create_metastore_provisions_through_the_account_api(
        self, monkeypatch, local_account_server
    ):
        from rest_framework import status as http

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        _patch_default_factory(monkeypatch, local_account_server)
        RecordingHandler.json_script = [
            '{"metastore_id": "ms-1", "name": "meshant-shared", "region": "us-east-1"}',
        ]

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/metastores/",
            {
                "tenant_id": str(tenant.id),
                "name": "meshant-shared",
                "region": "us-east-1",
                "storage_root": "s3://meshant/metastore",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_201_CREATED, resp.content
        assert resp.json()["metastore_id"] == "ms-1"
        recorded = RecordingHandler.requests
        assert len(recorded) == 1
        assert recorded[0]["path"] == f"/api/2.0/accounts/{account.account_id}/metastores"

    def test_the_registry_validation_is_never_bypassed(self, monkeypatch, local_account_server):
        require_dns()
        from rest_framework import status as http

        from hub.apps.databricks_admin.models import DatabricksWorkspace

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        _patch_default_factory(monkeypatch, local_account_server)
        RecordingHandler.json_script = [
            '{"workspace_id": 7000000000000002, "workspace_name": "meshant-ws", '
            '"deployment_name": "dbc-evil", "workspace_url": "https://evil.example.com", '
            '"workspace_status": "PROVISIONING"}',
        ]

        resp = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws",
                "aws_region": "us-east-1",
            },
            format="json",
        )

        assert resp.status_code == http.HTTP_400_BAD_REQUEST, (
            "a non-Databricks-family host is refused by the EXISTING registry validation"
        )
        assert not DatabricksWorkspace.objects.filter(tenant=tenant).exists(), (
            "no partial registry state for a rejected host"
        )


class TestServiceShape:
    def test_service_refuses_before_any_client_build(self):
        from rest_framework.exceptions import PermissionDenied

        from hub.apps.databricks_admin import account_ops

        tenant = TenantFactory.create_tenant()  # flag off
        account = _account()
        _signoff(account)
        calls = []

        def factory(account_):
            calls.append(account_)
            raise AssertionError("the client factory must never be invoked")

        with pytest.raises(PermissionDenied) as excinfo:
            account_ops.provision_workspace(
                account,
                tenant,
                workspace_name="meshant-ws",
                aws_region="us-east-1",
                client_factory=factory,
            )
        assert excinfo.value.code == "DATABRICKS_WORKSPACE_PROVISIONING_DISABLED"
        assert calls == []

    def test_service_requires_aws_region_before_any_network(self):
        from hub.apps.databricks_admin import account_ops

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)

        with pytest.raises(ValueError, match="aws_region"):
            account_ops.provision_workspace(
                account,
                tenant,
                workspace_name="meshant-ws",
                aws_region="",  # blank VALUE → ValueError before any network
                client_factory=lambda _account: (_ for _ in ()).throw(
                    AssertionError("the client factory must never be invoked")
                ),
            )
