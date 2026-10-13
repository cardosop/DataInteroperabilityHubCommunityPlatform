"""P8 (openspec add-databricks-account-plane task 8.6) — the
JOURNEY-DB-016 / UC-DB-016 backend journey pins: the platform admin
provisions a workspace from the linked Databricks account (flag ON +
recorded DPO/Legal signoff) through the REAL account API, the registry
row attaches to the target tenant through the EXISTING validation, and
the cross-tenant estate summary — the admin-DB read surface — reflects
the provisioned estate. The refusal leg proves the D3 triple fails
closed with ZERO network, and the RBAC leg proves a non-platform caller
gets the prose error table's 403 PERMISSION_DENIED.

NO MOCKS: real Postgres rows (account via the forced admin alias, target
tenant, signoff user, registry row), the PRODUCTION ``DatabricksAccountClient``
over a REAL threaded local account-API server (the ``_http.py``
RecordingHandler convention), the REAL DRF views over real HTTP with
``force_authenticate``. The sanctioned seam is the service's
default-client-factory symbol (the 8.3 recorder convention) — the refusal
pin records ZERO factory invocations so a broken gate could never reach
the real account host. The audit events the prose journey names
(``DATABRICKS_ACCOUNT_LINKED/METASTORE_CREATED/WORKSPACE_PROVISIONED``)
ship with task 8.5 — the journey pins here drive the LANDED surfaces
(model, provisioning, estate summary); the prose docs carry the 8.5
scope note.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

TOKEN = "dapi-account-token"
ESTATE_URL = "/api/v1/databricks/estate-summary/"


def _platform_user():
    from hub.apps.users.models import User, UserStatus

    user = User.objects.create_user(
        email=f"j016-{uuid.uuid4().hex[:8]}@meshant.test",
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
    pin asserts ZERO invocations)."""
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


class TestJOURNEYDB016ProvisionWorkspaceFromAccount:
    """The journey the prose doc pins (docs/mvpdocs/use-cases/UC-DB-016.md
    "Phase P8 Test"): the platform admin provisions a workspace from the
    account, the estate summary — the admin-DB aggregate — reflects it,
    the D3 triple refuses with zero network, and the RBAC gate holds."""

    @pytest.mark.journey("JOURNEY-DB-016")
    @pytest.mark.uc("UC-DB-016")
    def test_admin_db_path(self, monkeypatch, local_http_server):
        # The FULL spine: the account row lives on the admin DB (the 8.2
        # forced-alias manager), the provisioning runs through the real
        # account API, the registry row attaches under tenant_context, and
        # the estate summary — read over the admin alias (BYPASSRLS) —
        # reports the provisioned workspace across the platform surface.
        require_dns()
        from hub.apps.databricks_admin.tests._http import RecordingHandler

        tenant = _enable_flag(TenantFactory.create_tenant())
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_http_server)

        # The account API's workspace-create answer: the ONLY transport
        # value the attach trusts (a *.cloud.databricks.com family host
        # that passes the registry's SSRF + residency validation).
        import json

        RecordingHandler.json_script = [
            json.dumps(
                {
                    "deployment_name": "dbc-8fe1",
                    "workspace_url": f"https://{REAL_HOST}",
                }
            )
        ]

        response = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws-j016",
                "aws_region": "us-east-1",
            },
            format="json",
        )
        assert response.status_code == 201, response.content
        assert len(calls) == 1, "the sanctioned path builds exactly one account client"

        from hub.apps.databricks_admin.models import DatabricksWorkspace

        attached = DatabricksWorkspace.objects.get(tenant=tenant)
        assert attached.host == REAL_HOST, "the registry row carries the provisioned host"

        # The estate summary (the admin-DB read surface) reports the
        # provisioned workspace — one derived row, no cached drift. The
        # summary paginates (50 rows/page) and shared/clone DBs carry
        # residue estate rows, so the pin WALKS the pages until the
        # tenant's row appears (pagination-proof, the residue-proof
        # convention).
        estate_row = None
        url: str | None = ESTATE_URL
        for _ in range(10):  # a bounded walk — the row must appear
            assert url is not None, "estate summary pagination exhausted"
            estate = _client(_platform_user()).get(url)
            assert estate.status_code == 200, estate.content
            body = estate.json()
            estate_row = next(
                (r for r in body["results"] if r["tenant_id"] == str(tenant.id)),
                None,
            )
            if estate_row is not None:
                break
            url = body.get("next")
        assert estate_row is not None, "the provisioned tenant must appear in the estate summary"
        assert estate_row["tenant_name"] == tenant.name
        assert estate_row["workspace_count"] == 1
        assert estate_row["workspaces_by_state"] == {"REGISTERED": 1}, (
            "the attached registry row lands in its default REGISTERED state"
        )

    def test_provisioning_is_refused_without_flag_or_signoff(self, monkeypatch, local_http_server):
        # The D3 triple fails closed: flag OFF → 403 with the classified
        # code; signoff missing → 403 with the classified code; ZERO
        # network in both legs.
        from rest_framework import status as http

        from hub.apps.databricks_admin.tests._http import RecordingHandler

        tenant = TenantFactory.create_tenant()  # flag default-off
        account = _account()
        _signoff(account)
        calls = _patch_default_factory(monkeypatch, local_http_server)

        flag_off = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{account.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws-j016",
                "aws_region": "us-east-1",
            },
            format="json",
        )
        assert flag_off.status_code == http.HTTP_403_FORBIDDEN
        assert flag_off.json()["error"]["code"] == "DATABRICKS_WORKSPACE_PROVISIONING_DISABLED"

        # A DIFFERENT account with the flag ON but NO signoff record.
        unsigned = _account()
        calls_unsigned = _patch_default_factory(monkeypatch, local_http_server)
        signoff_missing = _client(_platform_user()).post(
            f"/api/v1/databricks/accounts/{unsigned.id}/workspaces/",
            {
                "tenant_id": str(tenant.id),
                "workspace_name": "meshant-ws-j016",
                "aws_region": "us-east-1",
            },
            format="json",
        )
        assert signoff_missing.status_code == http.HTTP_403_FORBIDDEN
        assert signoff_missing.json()["error"]["code"] == "DATABRICKS_PROVISIONING_SIGNOFF_MISSING"
        assert calls == [], "refusals never build a client"
        assert calls_unsigned == [], "refusals never build a client"
        assert RecordingHandler.requests == [], "ZERO network for refused provisioning"

    def test_non_platform_caller_gets_the_prose_403(self):
        # The prose error table: an authenticated NON-platform caller hits
        # the account-plane read surface and gets 403 PERMISSION_DENIED.
        from rest_framework import status as http

        from hub.apps.users.models import User, UserStatus

        tenant = TenantFactory.create_tenant()
        bystander = User.objects.create_user(
            email=f"j016-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        response = _client(bystander).get(ESTATE_URL)
        assert response.status_code == http.HTTP_403_FORBIDDEN
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
