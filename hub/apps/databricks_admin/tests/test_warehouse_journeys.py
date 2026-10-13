"""Journey pins for the P3 SQL-warehouses surface (openspec
add-databricks-sql-warehouses task 3.9) — JOURNEY-DB-010 (Manage SQL
Warehouses) + UC-DB-010 (Manage SQL Warehouse Lifecycle).

Class/method names are PINNED by the UC docs' "Phase P3 Test" field
(docs/mvpdocs/use-cases/UC-DB-010.md) — renaming them breaks the
docs↔test drift gates (GATE-28).

No mocks: real Postgres rows (tenant/workspace/mirror/binding), real
RBAC + flag gating, the REAL API viewset, the REAL OBO provider with
the access token seeded in the REAL Redis cache (get_bearer never
touches the network), the PRODUCTION compute client against a REAL
local HTTP server (the 3.7 view-test seam), the REAL 3.8 audit
chokepoint, the REAL 3.4 creation chain, the REAL 3.5 pool, and the
REAL 3.6 http_path linkage.
"""

import json
import uuid

import pytest
from django.db import transaction
from rest_framework.test import APIClient

from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_sql_warehouse_views import (
    _seed_mirror,
    _seed_workspace,
    _url,
)
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from tests.factories import TenantFactory

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.journey("JOURNEY-DB-010"),
    pytest.mark.uc("UC-DB-010"),
]

CHAIN_NAME = "databricks.warehouse.create"


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def _chain_payload(**overrides):
    payload = {"name": "journey-wh", "size": "S", "auto_stop_mins": 30}
    payload.update(overrides)
    return payload


def _warehouse_payload(warehouse_id="wh-1", state="STOPPED"):
    return {
        "id": warehouse_id,
        "name": f"wh-{warehouse_id}",
        "state": state,
        "serverless": True,
        "size": None,
        "auto_stop_mins": 30,
    }


class TestJOURNEYDB010ManageSQLWarehouses:
    """A data engineer manages the tenant's SQL warehouses: the mirror
    lists the fleet, lifecycle actions drive the REAL compute client
    and refresh the mirror (never an invented state), the 3.8 audit
    chokepoint emits per performed action, creation is chain-gated
    BEFORE any network call, the 3.5 pool can never cross tenants, and
    live-query connections derive their http_path from the warehouse
    id.

    Plain class (not TestCase) — pytest fixtures cannot serve TestCase
    methods (the 0.8 trap); the Test* prefix satisfies python_classes
    (the 1.3 trap). No inheritance from the 3.7 view-test class — that
    would collect the parent's pins here as duplicates.
    """

    # ── the lifecycle-leg setup (the 3.7 view-test seam) ─────────────

    def _setup(self, with_binding=True, with_cache=True, redis_client=None):
        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.workspace = _seed_workspace(self.tenant)
        self.mirror = _seed_mirror(self.workspace, warehouse_id="wh-1", state="STOPPED")
        self.binding = None
        if with_binding:
            from hub.apps.databricks_admin.models import DatabricksUserBinding

            self.binding = DatabricksUserBinding.objects.create(
                tenant=self.tenant,
                user=self.admin,
                workspace=self.workspace,
                databricks_sub=f"sub-{uuid.uuid4().hex[:8]}",
                databricks_email=self.admin.email,
            )
            from hub.apps.tenants.models import TenantConfig

            config = TenantConfig.objects.get_or_create(tenant=self.tenant)[0]
            sso = config.get_sso_config()
            sso["databricks"] = {
                "host": REAL_HOST,
                "client_id": "client-abc",
                "redirect_uri": "https://hub.example.com/auth/databricks/callback",
            }
            config.sso_config = sso
            config.save()
            if with_cache:
                from hub.apps.databricks_admin.obo_tokens import OBOAccessTokenCache

                OBOAccessTokenCache(redis_client=redis_client).set(
                    self.binding.id, "dapi-wh-access", 300
                )

    def _patch_client_factory(self, monkeypatch, port):
        from hub.apps.databricks_admin import sql_warehouse_views as views_module
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.obo_tokens import OBOTokenProvider

        def fake_factory(workspace, _identity):
            provider = OBOTokenProvider(
                binding=self.binding,
                oidc_client_id="client-abc",
                oidc_base_url=f"http://127.0.0.1:{port}",
            )
            return DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(workspace.tenant_id),
                obo_provider=provider,
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
            )

        monkeypatch.setattr(views_module, "_build_uc_client", fake_factory)

    # ── the journey pins ─────────────────────────────────────────────

    def test_lifecycle_state_transitions(self, monkeypatch, local_http_server, redis_13):
        self._setup(redis_client=redis_13)
        self.mirror.state = "RUNNING"
        self.mirror.save(update_fields=["state"])
        _seed_mirror(
            self.workspace, warehouse_id="wh-2", state="STOPPED", serverless=False, size="M"
        )
        self._patch_client_factory(monkeypatch, local_http_server)
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="RUNNING")),  # the state GET
            "{}",  # the stop POST's empty-body answer
            json.dumps({"warehouses": [_warehouse_payload(state="STOPPING")]}),  # the refresh LIST
        ]

        # The mirror-first listing surfaces the fleet (zero network on
        # the READ leg — every request so far is zero).
        response = _client(self.admin).get(_url(self.workspace.id))
        assert response.status_code == 200, response.content
        rows = {row["warehouse_id"]: row for row in response.json()["results"]}
        assert set(rows) == {"wh-1", "wh-2"}
        assert rows["wh-2"]["size"] == "M"
        assert rows["wh-2"]["serverless"] is False
        assert RecordingHandler.requests == [], "the mirror-first list never touches the wire"

        # The lifecycle leg: STOP through the REAL endpoint → the wire
        # POST → the mirror follows the compute API.
        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/stop/"))
        assert response.status_code == 200, response.content
        posts = [r for r in RecordingHandler.requests if r["method"] == "POST"]
        assert len(posts) == 1
        assert posts[0]["path"] == "/api/2.0/sql/warehouses/wh-1/stop"

        self.mirror.refresh_from_db()
        assert self.mirror.state == "STOPPING", "the mirror reports the compute API's state"
        assert response.json()["state"] == "STOPPING"

        # The 3.8 chokepoint: one audit row per performed operation.
        from hub.apps.audit.models import AuditEvent

        event = AuditEvent.objects.get(
            tenant=self.tenant,
            resource_type="DATABRICKS_WAREHOUSE",
            action="STOPPED",
        )
        assert str(event.resource_id) == str(self.mirror.id)
        assert event.details_json["warehouse_id"] == "wh-1"
        assert event.actor_user_id == self.admin.id

    def test_start_fails_closed_without_a_binding(self):
        """The identity leg of the journey: without a Databricks user
        binding the action fails closed (502) with ZERO network calls —
        never a service-credential fallback on interactive paths."""
        self._setup(with_binding=False)
        response = _client(self.admin).post(_url(self.workspace.id, "wh-1/start/"))
        assert response.status_code == 502, response.content
        assert response.json()["code"] == "DATABRICKS_OBO_REFRESH_FAILED"
        assert RecordingHandler.requests == [], "the fail-closed leg never touches the wire"
        self.mirror.refresh_from_db()
        assert self.mirror.state == "STOPPED", "a refused action never mutates the mirror"

    def test_creation_chain_gates_the_size_by_tier_before_any_network(self):
        """The creation gate: the tenant's plan tier allowlists sizes;
        a gated size fails with the classified code and ZERO network
        calls, an allowed size passes (the consumer endpoint invokes
        this chain inside transaction.atomic() before any compute
        call)."""
        from hub.apps.core.business_rules.chains import execute_chain

        require_dns()
        tenant = TenantFactory.create_tenant()  # plan-less → the ACTIVE free plan baseline
        _make_workspace(tenant)

        with transaction.atomic():
            refused = execute_chain(CHAIN_NAME, tenant=tenant, payload=_chain_payload(size="L"))
        assert refused["outcome"] == "FAIL", refused
        assert any("[DATABRICKS_WAREHOUSE_TIER_FORBIDDEN]" in err for err in refused["errors"]), (
            refused["errors"]
        )
        assert RecordingHandler.requests == [], "the chain has no network surface"

        with transaction.atomic():
            passed = execute_chain(CHAIN_NAME, tenant=tenant, payload=_chain_payload(size="S"))
        assert passed["outcome"] == "PASS", passed

    def test_pool_never_crosses_tenants(self):
        """The 3.5 structural isolation: tenant A at capacity raises
        EXHAUSTED while tenant B's borrow succeeds; a reused borrow
        returns the SAME connection; a factory result whose tenant
        marker disagrees is refused before it is pooled."""
        from hub.apps.databricks_admin.sql_warehouse_pool import (
            DatabricksWarehousePoolError,
            SqlWarehousePool,
        )

        class _Conn:
            def __init__(self, tenant_id):
                self._tenant_id = tenant_id
                self.closed = False

            def close(self):
                self.closed = True

        made: list[_Conn] = []

        def factory(tenant_id):
            conn = _Conn(tenant_id)
            made.append(conn)
            return conn

        pool = SqlWarehousePool(max_per_tenant=1, idle_timeout_s=3600, reap_interval_s=3600)
        a1 = pool.borrow("tenant-a", "wh-1", factory)
        with pytest.raises(DatabricksWarehousePoolError) as exhausted:
            pool.borrow("tenant-a", "wh-1", factory)
        assert exhausted.value.code == "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED"

        b1 = pool.borrow("tenant-b", "wh-1", factory)  # B is untouched by A's exhaustion
        pool.release(a1)
        a2 = pool.borrow("tenant-a", "wh-1", factory)  # reuse, not a new connection
        assert a2 is a1
        assert len(made) == 2, "exactly one connection per tenant was created"

        # The tenant's slot must be FREE for the factory to run (the
        # slot spans every borrow, before the factory — the 3.5-review
        # semantics), so release first, then ask for a DIFFERENT
        # warehouse with a mismatching factory.
        pool.release(a2)
        refused = _Conn("tenant-b")
        with pytest.raises(DatabricksWarehousePoolError) as mismatch:
            pool.borrow("tenant-a", "wh-2", lambda _tid: refused)
        assert mismatch.value.code == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert refused.closed, "the refused connection was closed, never served"
        assert ("tenant-a", "wh-2") not in pool._entries, "the refused connection never pooled"

        pool.release(b1)
        pool.stop()
        assert a1.closed, "stop() closes tenant A's connection"
        assert b1.closed, "stop() closes tenant B's connection"

    def test_http_path_is_derived_never_stored(self):
        """The 3.6 linkage: the connection's http_path is DERIVED from
        the mirror row's warehouse id (the connector's canonical form);
        the mirror carries no http_path field — the path is never
        stored twice."""
        from hub.apps.databricks_admin.models import (
            DatabricksCloud,
            DatabricksCredential,
            DatabricksCredentialAuthMode,
            DatabricksSqlWarehouse,
            DatabricksWorkspace,
        )
        from hub.apps.warehouses.models import WarehouseConnection

        require_dns()
        tenant = TenantFactory.create_tenant()
        workspace = DatabricksWorkspace.objects.create(
            tenant=tenant,
            name=f"prod-{uuid.uuid4().hex[:6]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
        )
        credential = DatabricksCredential.objects.create(
            workspace=workspace,
            auth_mode=DatabricksCredentialAuthMode.PAT,
            config={"token": "dapi-journey"},
        )
        mirror = DatabricksSqlWarehouse.objects.create(
            workspace=workspace,
            warehouse_id=f"wh-journey-{uuid.uuid4().hex[:6]}",
            name="analytics",
            state="RUNNING",
        )

        conn = WarehouseConnection.derive_from_sql_warehouse(workspace, credential, mirror)
        assert conn.get_config()["http_path"] == f"/sql/1.0/warehouses/{mirror.warehouse_id}"
        assert not any(
            field.name == "http_path" for field in DatabricksSqlWarehouse._meta.fields
        ), "the mirror never stores the derived path"
