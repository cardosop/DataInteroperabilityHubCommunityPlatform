"""P8 (openspec add-databricks-account-plane task 8.5, design D5) — the
account-plane audit battery.

Every account-level operation emits its OWN audit event —
``DATABRICKS_ACCOUNT_LINKED`` / ``DATABRICKS_METASTORE_CREATED`` /
``DATABRICKS_WORKSPACE_PROVISIONED`` — each carrying its resource ids
(account and/or workspace), BEST-EFFORT (an audit-DB outage never blocks
the operation — the Phase 273 discipline). The vocabulary registration is
pinned (constants + the ``__all__`` list), and the spec's three-events
flow runs end-to-end: link → metastore create → workspace provision.

No mocks: real Postgres rows (account via the admin alias, tenant,
signoff, registry row, the audit table), the PRODUCTION
``DatabricksAccountClient`` over a REAL threaded local account-API
server, and the REAL DRF views over real HTTP. The sanctioned seams are
the client factory (the 8.3 convention) and the audit-utils symbol for
the outage pin (the operation must succeed while ``create_audit_event``
raises — the seam IS the injection point, everything else real).
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
        email=f"aud-{uuid.uuid4().hex[:8]}@meshant.test",
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


def _link(client, *, account_id=None, display_name=None, token=TOKEN):
    """Link an account through the REAL view and return the response."""
    return client.post(
        "/api/v1/databricks/accounts/",
        {
            "account_id": account_id or str(uuid.uuid4()),
            "display_name": display_name or f"acct-{uuid.uuid4().hex[:8]}",
            "credential": {"token": token},
        },
        format="json",
    )


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


def _enable_flag(tenant):
    tenant.databricks_workspace_provisioning_enabled = True
    tenant.save(update_fields=["databricks_workspace_provisioning_enabled"])
    return tenant


def _patch_default_factory(monkeypatch, port):
    from hub.apps.databricks_admin.account_client import DatabricksAccountClient

    def factory(account):
        return DatabricksAccountClient(
            str(account.account_id),
            account.get_config(),
            base_url=f"http://127.0.0.1:{port}",
            retry_base_delay=0.01,
            retry_max_delay=0.02,
        )

    from hub.apps.databricks_admin import account_ops

    monkeypatch.setattr(account_ops, "_default_client_factory", factory)


def _events(**filters):
    from hub.apps.audit.models import AuditEvent

    return AuditEvent.objects.filter(**filters)


class TestVocabularyRegistration:
    def test_the_three_events_are_registered_in_the_vocabulary(self):
        from hub.apps.audit import event_types

        for name in (
            "DATABRICKS_ACCOUNT_LINKED",
            "DATABRICKS_METASTORE_CREATED",
            "DATABRICKS_WORKSPACE_PROVISIONED",
        ):
            assert getattr(event_types, name) == name, f"{name} constant missing"
            assert name in event_types.__all__, f"{name} missing from the __all__ vocabulary"


class TestAccountLinkAudit:
    def test_linking_an_account_emits_account_linked(self):
        from rest_framework import status as http

        from hub.apps.databricks_admin.models import DatabricksAccount

        account_id = str(uuid.uuid4())
        resp = _link(_client(_platform_user()), account_id=account_id, display_name="meshant-prod")

        assert resp.status_code == http.HTTP_201_CREATED, resp.content
        row = DatabricksAccount.objects.get(account_id=account_id)
        events = list(_events(action="DATABRICKS_ACCOUNT_LINKED", resource_id=str(row.id)))
        assert len(events) == 1, "exactly one ACCOUNT_LINKED event"
        event = events[0]
        assert str(event.resource_id) == str(row.id), "the event carries the account row id"
        assert event.details_json["account_id"] == account_id, "the event carries the account id"
        assert event.details_json["display_name"] == "meshant-prod"

    def test_duplicate_link_is_refused_with_409_and_no_second_event(self):
        from rest_framework import status as http

        account_id = str(uuid.uuid4())
        client = _client(_platform_user())
        first = _link(client, account_id=account_id)
        assert first.status_code == http.HTTP_201_CREATED
        second = _link(client, account_id=account_id)

        assert second.status_code == http.HTTP_409_CONFLICT
        assert second.json()["error"]["code"] == "DATABRICKS_ACCOUNT_ALREADY_LINKED"
        assert (
            _events(action="DATABRICKS_ACCOUNT_LINKED")
            .filter(details_json__account_id=account_id)
            .count()
            == 1
        ), "the refused duplicate never emits"

    def test_non_platform_admin_cannot_link(self):
        from rest_framework import status as http

        from hub.apps.users.models import User, UserStatus

        bystander = User.objects.create_user(
            email=f"bystander-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            status=UserStatus.ACTIVE,
        )
        resp = _link(_client(bystander))

        assert resp.status_code == http.HTTP_403_FORBIDDEN
        assert resp.json()["error"]["code"] == "PERMISSION_DENIED"


class _ProvisioningMixin:
    def _provision_metastore(self, account, tenant, monkeypatch, port):
        from hub.apps.databricks_admin import account_ops

        _patch_default_factory(monkeypatch, port)
        RecordingHandler.json_script = [
            '{"metastore_id": "ms-1", "name": "meshant-shared", "region": "us-east-1"}',
        ]
        return account_ops.provision_metastore(
            account, tenant, name="meshant-shared", region="us-east-1"
        )

    def _provision_workspace(self, account, tenant, monkeypatch, port):
        from hub.apps.databricks_admin import account_ops

        _patch_default_factory(monkeypatch, port)
        RecordingHandler.json_script = [
            '{"workspace_id": 7000000000000001, "workspace_name": "meshant-ws", '
            f'"deployment_name": "dbc-8fe1", "workspace_url": "https://{REAL_HOST}", '
            '"workspace_status": "PROVISIONING"}',
        ]
        return account_ops.provision_workspace(
            account, tenant, workspace_name="meshant-ws", aws_region="us-east-1"
        )

    def _account(self):
        from hub.apps.databricks_admin.models import DatabricksAccount

        account = DatabricksAccount(
            account_id=uuid.uuid4(),
            display_name=f"acct-{uuid.uuid4().hex[:8]}",
        )
        account.set_config({"token": TOKEN})
        account.save()
        _signoff(account)
        return account


class TestProvisioningAudit(_ProvisioningMixin):
    def test_metastore_creation_emits_metastore_created(self, monkeypatch, local_account_server):
        tenant = _enable_flag(TenantFactory.create_tenant())
        account = self._account()
        envelope = self._provision_metastore(account, tenant, monkeypatch, local_account_server)

        events = list(_events(action="DATABRICKS_METASTORE_CREATED", resource_id=str(account.id)))
        assert len(events) == 1, "exactly one METASTORE_CREATED event"
        event = events[0]
        assert str(event.resource_id) == str(account.id), "the event carries the account row id"
        assert event.details_json["account_id"] == str(account.account_id)
        assert event.details_json["metastore_id"] == envelope["metastore_id"]
        assert event.details_json["tenant_id"] == str(tenant.id)

    def test_workspace_provisioning_emits_workspace_provisioned(
        self, monkeypatch, local_account_server
    ):
        require_dns()
        tenant = _enable_flag(TenantFactory.create_tenant())
        account = self._account()
        workspace = self._provision_workspace(account, tenant, monkeypatch, local_account_server)

        events = list(
            _events(action="DATABRICKS_WORKSPACE_PROVISIONED", resource_id=str(workspace.id))
        )
        assert len(events) == 1, "exactly one WORKSPACE_PROVISIONED event"
        event = events[0]
        assert str(event.resource_id) == str(workspace.id), "the event carries the registry row id"
        assert event.tenant_id == tenant.id, "the event belongs to the target tenant"
        assert event.details_json["account_id"] == str(account.account_id)
        assert event.details_json["workspace_id"] == 7000000000000001

    def test_the_full_flow_emits_three_distinct_events(self, monkeypatch, local_account_server):
        # The spec scenario: "GIVEN a linked account that provisions a
        # metastore and then a workspace WHEN each operation completes
        # THEN three distinct audit events exist — one per operation —
        # each carrying its own resource ids".
        require_dns()
        tenant = _enable_flag(TenantFactory.create_tenant())
        link_resp = _link(_client(_platform_user()))
        assert link_resp.status_code == 201
        from hub.apps.databricks_admin.models import DatabricksAccount

        account = DatabricksAccount.objects.get(id=link_resp.json()["id"])
        _signoff(account)
        self._provision_metastore(account, tenant, monkeypatch, local_account_server)
        workspace = self._provision_workspace(account, tenant, monkeypatch, local_account_server)

        assert _events(action="DATABRICKS_ACCOUNT_LINKED", resource_id=str(account.id)).exists()
        assert _events(action="DATABRICKS_METASTORE_CREATED", resource_id=str(account.id)).exists()
        assert _events(
            action="DATABRICKS_WORKSPACE_PROVISIONED", resource_id=str(workspace.id)
        ).exists(), "three distinct events — one per operation, each tied to its fresh ids"


class TestBestEffort(_ProvisioningMixin):
    def test_an_audit_outage_never_blocks_any_operation(self, monkeypatch, local_account_server):
        # D5 / the Phase 273 discipline: the audit write is best-effort.
        # The audit-utils symbol is the seam — everything else real.
        require_dns()
        import hub.apps.audit.utils as audit_utils

        def _audit_down(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        monkeypatch.setattr(audit_utils, "create_audit_event", _audit_down)

        # The LINK still succeeds.
        link_resp = _link(_client(_platform_user()))
        assert link_resp.status_code == 201, "a link never waits on the audit write"

        from hub.apps.databricks_admin.models import DatabricksAccount

        account = DatabricksAccount.objects.get(id=link_resp.json()["id"])
        _signoff(account)
        tenant = _enable_flag(TenantFactory.create_tenant())

        # The metastore create still returns the envelope.
        envelope = self._provision_metastore(account, tenant, monkeypatch, local_account_server)
        assert envelope["metastore_id"] == "ms-1"

        # The workspace still attaches its registry row.
        workspace = self._provision_workspace(account, tenant, monkeypatch, local_account_server)
        from hub.apps.databricks_admin.models import DatabricksWorkspace

        assert DatabricksWorkspace.objects.filter(id=workspace.id).exists()
