"""The 3.10 acceptance pins — the create → start → query → stop
round-trip, and the pool-isolation proof.

The umbrella acceptance: "Create → start → query → stop round-trip on
mocks; pool isolation proven; all DoD gates green." Following the repo's
no-mocks policy the round-trip runs against REAL transports — real
Postgres rows (tenant/plan/workspace/mirror/audit), the REAL chain
runner, the REAL lifecycle chokepoint, the REAL compute client, the REAL
statement executor and the REAL mirror refresh — with every compute
response served from the ``sql_warehouse_roundtrip.json`` fixture
through a REAL threaded HTTP server (the 3.10 fixture convention; the
strongest evidence supersedes the "on mocks" wording, the 0.19 precedent).

The round trip:

1. **create** — the 3.4 chain gates the request (tier + quota, zero
   network); the lifecycle chokepoint creates through the compute client
   and emits ``CREATED`` (no mirror row yet — the id lives in details).
2. **mirror** — the 3.2 delta-diff refreshes; the new row reports the
   compute API's STARTING state (never invented).
3. **start** — idempotent-state aware: the STARTING warehouse makes the
   START a no-op success; NO ``STARTED`` event (nothing was performed).
4. **query** — the P0 statement executor runs ``SELECT 1`` against the
   warehouse id through the real submit surface; the fixture's terminal
   SUCCEEDED payload carries the result rows.
5. **stop** — the RUNNING warehouse stops for real: the wire POST fires,
   ``STOPPED`` is emitted with the mirror row's pk, and the final
   refresh reports the compute API's STOPPING state.

The request trail (method, path) is asserted in ORDER — the round trip
is pinned as one continuous wire conversation, not five disconnected
calls. The pool-isolation proof then runs the 3.5 structural guarantee
with REAL clients: tenant A's exhaustion never touches tenant B, a
wrong-marker factory result is closed and refused, and stop() closes
every pooled transport.
"""

import json
import uuid

import pytest
from django.db import transaction

from hub.apps.databricks_admin.tests._fixtures import load_fixture_steps, require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_change_requests import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _make_user
from hub.apps.databricks_admin.tests.test_warehouse_create_chain import _plan
from hub.apps.tenants.models import PlanTier
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)

CHAIN_NAME = "databricks.warehouse.create"
ROUNDTRIP_FIXTURE = "sql_warehouse_roundtrip"
WAREHOUSE_ID = "wh-rt-1"


def _raw_client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t1",
        credential_config={"token": "dapi-wh"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,  # the 1.7 delegation convention — the test owns the transport
    )


def _trail():
    return [(r["method"], r["path"]) for r in RecordingHandler.requests]


class TestCreateStartQueryStopRoundtrip:
    def _seed(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        plan = _plan(tier=PlanTier.FREE, limits={"max_databricks_warehouses": 2})
        self.tenant.plan = plan
        self.tenant.save(update_fields=["plan"])
        self.workspace = _make_workspace(self.tenant)
        self.actor = _make_user(
            self.tenant, f"wh-rt-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )

    def test_the_full_round_trip(self, local_http_server):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.core.business_rules.chains import execute_chain
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse
        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor
        from hub.apps.databricks_admin.sql_warehouse_client import DatabricksComputeClient
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import (
            create_sql_warehouse,
            start_sql_warehouse,
            stop_sql_warehouse,
        )
        from hub.apps.databricks_admin.sql_warehouses import refresh_sql_warehouse_mirror

        self._seed()
        RecordingHandler.json_script = load_fixture_steps(ROUNDTRIP_FIXTURE)
        raw = _raw_client(local_http_server)
        compute = DatabricksComputeClient(raw)

        # 1. create — the chain gates FIRST (tier + quota, zero network).
        with transaction.atomic():
            gated = execute_chain(
                CHAIN_NAME,
                tenant=self.tenant,
                payload={"name": "roundtrip-wh", "size": "S", "auto_stop_mins": 30},
            )
        assert gated["outcome"] == "PASS", gated
        assert RecordingHandler.requests == [], "the chain has no network surface"

        warehouse_id = create_sql_warehouse(
            self.workspace,
            client=compute,
            name="roundtrip-wh",
            serverless=False,
            auto_stop_mins=30,
            size="S",
            actor_user=self.actor,
        )
        assert warehouse_id == WAREHOUSE_ID

        created_event = AuditEvent.objects.get(
            tenant=self.tenant,
            resource_type="DATABRICKS_WAREHOUSE",
            action="CREATED",
        )
        assert created_event.resource_id is None, "a just-created warehouse has no mirror row yet"
        assert created_event.details_json["warehouse_id"] == WAREHOUSE_ID
        assert created_event.actor_user_id == self.actor.id

        # 2. the mirror follows — the new row reports STARTING (the
        # compute API's state, never invented).
        counters = refresh_sql_warehouse_mirror(self.workspace, client=raw)
        assert counters == {"created": 1, "updated": 0, "unchanged": 0, "deleted": 0}, counters
        mirror = DatabricksSqlWarehouse.objects.get(workspace=self.workspace)
        assert mirror.state == "STARTING"

        # 3. start — the STARTING warehouse makes the START a no-op
        # success; NOTHING was performed, so no STARTED event exists.
        assert (
            start_sql_warehouse(self.workspace, WAREHOUSE_ID, client=compute, actor_user=self.actor)
            is None
        )
        assert not AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="DATABRICKS_WAREHOUSE",
            action="STARTED",
        ).exists(), "a no-op start emits NOTHING (per-operation events, D6)"

        # The warehouse finished starting — the mirror follows.
        counters = refresh_sql_warehouse_mirror(self.workspace, client=raw)
        assert counters == {"created": 0, "updated": 1, "unchanged": 0, "deleted": 0}, counters
        mirror.refresh_from_db()
        assert mirror.state == "RUNNING"

        # 4. query — the statement executor runs against the warehouse.
        executor = SqlStatementExecutor(client=raw, poll_interval_seconds=0.05)
        result = executor.execute("SELECT 1", warehouse_id=WAREHOUSE_ID)
        assert result.statement_id == "s-rt-1"
        assert result.state == "SUCCEEDED"
        assert result.columns == ["1"]
        assert result.rows == [["1"]]
        assert result.row_count == 1
        executor._external_client.close()

        submit = next(
            r for r in RecordingHandler.requests if r["path"] == "/api/2.0/sql/statements"
        )
        assert json.loads(submit["body"]) == {
            "statement": "SELECT 1",
            "wait_timeout": "10s",
            "warehouse_id": WAREHOUSE_ID,
        }

        # 5. stop — a real STOP: the wire POST fires, the STOPPED event
        # anchors the mirror row's pk, the final refresh reports STOPPING.
        assert (
            stop_sql_warehouse(self.workspace, WAREHOUSE_ID, client=compute, actor_user=self.actor)
            == {}
        )
        stopped_event = AuditEvent.objects.get(
            tenant=self.tenant,
            resource_type="DATABRICKS_WAREHOUSE",
            action="STOPPED",
        )
        assert str(stopped_event.resource_id) == str(mirror.id)
        assert stopped_event.actor_user_id == self.actor.id

        counters = refresh_sql_warehouse_mirror(self.workspace, client=raw)
        assert counters == {"created": 0, "updated": 1, "unchanged": 0, "deleted": 0}, counters
        mirror.refresh_from_db()
        assert mirror.state == "STOPPING"

        # The wire conversation, in order — the round trip as ONE trail.
        assert _trail() == [
            ("POST", "/api/2.0/sql/warehouses"),  # create
            ("GET", "/api/2.0/sql/warehouses"),  # mirror refresh (STARTING)
            ("GET", f"/api/2.0/sql/warehouses/{WAREHOUSE_ID}"),  # start's state GET
            ("GET", "/api/2.0/sql/warehouses"),  # mirror refresh (RUNNING)
            ("POST", "/api/2.0/sql/statements"),  # the query leg
            ("GET", f"/api/2.0/sql/warehouses/{WAREHOUSE_ID}"),  # stop's state GET
            ("POST", f"/api/2.0/sql/warehouses/{WAREHOUSE_ID}/stop"),  # the STOP
            ("GET", "/api/2.0/sql/warehouses"),  # mirror refresh (STOPPING)
        ]

    def test_pool_isolation_is_proven_end_to_end(self):
        """The acceptance's second clause — the 3.5 structural guarantee
        with REAL clients: tenant A's exhaustion never touches tenant B,
        a factory result whose marker disagrees is closed and refused
        before it is pooled, a released borrow is REUSED, and stop()
        closes every pooled transport."""
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.sql_warehouse_pool import (
            DatabricksWarehousePoolError,
            SqlWarehousePool,
        )

        def factory(tenant_id):
            return DatabricksApiClient(
                base_url="http://127.0.0.1:1",  # never dialed — closed transports only
                tenant_id=tenant_id,
                credential_config={"token": "dapi-pool"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                use_breaker=False,  # the 1.7 delegation convention — the test owns the transport
            )

        pool = SqlWarehousePool(max_per_tenant=1, idle_timeout_s=3600, reap_interval_s=3600)
        a1 = pool.borrow("tenant-a", "wh-1", factory)
        with pytest.raises(DatabricksWarehousePoolError) as exhausted:
            pool.borrow("tenant-a", "wh-1", factory)
        assert exhausted.value.code == "DATABRICKS_WAREHOUSE_POOL_EXHAUSTED"

        b1 = pool.borrow("tenant-b", "wh-1", factory)  # B is untouched by A's exhaustion
        assert b1._tenant_id == "tenant-b"
        pool.release(a1)
        a2 = pool.borrow("tenant-a", "wh-1", factory)  # reuse, not a new client
        assert a2 is a1

        pool.release(a2)
        wrong = factory("tenant-b")
        with pytest.raises(DatabricksWarehousePoolError) as mismatch:
            pool.borrow("tenant-a", "wh-2", lambda _tid: wrong)
        assert mismatch.value.code == "DATABRICKS_WAREHOUSE_POOL_TENANT_MISMATCH"
        assert wrong._client.is_closed, "the refused client was closed, never served"
        assert ("tenant-a", "wh-2") not in pool._entries

        pool.release(b1)
        pool.stop()
        assert a1._client.is_closed, "stop() closes tenant A's pooled transport"
        assert b1._client.is_closed, "stop() closes tenant B's pooled transport"
