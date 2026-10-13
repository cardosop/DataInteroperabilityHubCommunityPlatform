"""TDD pins for the SQL warehouse lifecycle audit (openspec
add-databricks-sql-warehouses task 3.8) — the compute observability
contract.

``hub/apps/databricks_admin/sql_warehouse_lifecycle.py`` is the
lifecycle's SINGLE audit chokepoint (the 2.9 emit precedent): each
performed lifecycle operation emits one audit row
(resource_type=``DATABRICKS_WAREHOUSE``, action
CREATED/STARTED/STOPPED/RESIZED/DELETED) with tenant + actor
attribution and IDENTIFIERS-ONLY details (no credential material —
the 0.16 redaction contract). No-op start/stop (the 3.3 idempotency)
emit NOTHING; a failed state transition propagates
``DATABRICKS_WAREHOUSE_STATE_ERROR`` with NO audit row; an audit-DB
outage NEVER blocks the operation (the Phase 273 best-effort contract).

No mocks: real Postgres rows, the PRODUCTION compute client against a
REAL local HTTP server, REAL audit rows read back from the DB.
"""

import http.server
import json
import threading
import uuid

import pytest
from django.test import TestCase

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing, _make_user
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _client(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient
    from hub.apps.databricks_admin.sql_warehouse_client import DatabricksComputeClient

    return DatabricksComputeClient(
        DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id="t1",
            credential_config={"token": "dapi-wh"},
            timeout_ms=5000,
            max_retries=1,
            retry_base_delay=0.05,
            retry_max_delay=0.1,
            use_breaker=False,
        )
    )


def _warehouse_payload(warehouse_id="wh-1", state="RUNNING", **extra):
    payload = {
        "id": warehouse_id,
        "name": "etl-warehouse",
        "state": state,
        "serverless": True,
        "auto_stop_mins": 30,
    }
    payload.update(extra)
    return payload


class WarehouseLifecycleAuditTests(TestCase):
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.actor = _make_user(
            self.tenant, f"wh-audit-{uuid.uuid4().hex[:8]}@test.com", "TENANT_ADMIN"
        )
        self.workspace = _make_workspace(self.tenant)

    def _server(self):
        RecordingHandler.script = []
        RecordingHandler.requests = []
        RecordingHandler.json_script = []
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.shutdown)
        return port

    def _mirror_row(self, warehouse_id="wh-1", state="STOPPED"):
        from hub.apps.databricks_admin.models import DatabricksSqlWarehouse

        return DatabricksSqlWarehouse.objects.create(
            workspace=self.workspace,
            warehouse_id=warehouse_id,
            name=f"etl-{warehouse_id}",
            state=state,
        )

    def _audit_rows(self):
        from hub.apps.audit.models import AuditEvent

        return list(
            AuditEvent.objects.filter(
                tenant=self.tenant, resource_type="DATABRICKS_WAREHOUSE"
            ).order_by("timestamp")
        )

    # ── create ──────────────────────────────────────────────────────────

    def test_create_emits_created_with_identifiers_only(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import create_sql_warehouse

        port = self._server()
        RecordingHandler.json_script = [json.dumps(_warehouse_payload("wh-new"))]
        result = create_sql_warehouse(
            self.workspace,
            client=_client(port),
            name="etl-serverless",
            serverless=True,
            auto_stop_mins=30,
            actor_user=self.actor,
        )
        assert result == "wh-new"

        rows = self._audit_rows()
        assert len(rows) == 1
        row = rows[0]
        assert row.action == "CREATED"
        assert row.actor_user_id == self.actor.id
        assert row.resource_id is None, "no mirror row exists yet — the id lives in details"
        assert row.details_json == {
            "warehouse_id": "wh-new",
            "workspace_id": str(self.workspace.id),
        }, "identifiers only — never credential material"

    # ── start / stop ────────────────────────────────────────────────────

    def test_performed_start_emits_started_with_the_mirror_row_id(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import start_sql_warehouse

        mirror = self._mirror_row(state="STOPPED")
        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="STOPPED")),
            "",  # the start POST's empty-body answer
        ]
        result = start_sql_warehouse(
            self.workspace, "wh-1", client=_client(port), actor_user=self.actor
        )
        assert result == {}

        rows = self._audit_rows()
        assert len(rows) == 1
        assert rows[0].action == "STARTED"
        assert rows[0].resource_id == mirror.id, (
            "the mirror row's pk anchors the event when it exists"
        )
        assert rows[0].details_json["warehouse_id"] == "wh-1"

    def test_no_op_start_emits_nothing(self):
        # The 3.3 idempotency: START on a RUNNING warehouse is a no-op —
        # nothing happened, so NO audit row (the spec scenario's flip
        # side; per-operation events only).
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import start_sql_warehouse

        self._mirror_row(state="RUNNING")
        port = self._server()
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="RUNNING"))]
        result = start_sql_warehouse(
            self.workspace, "wh-1", client=_client(port), actor_user=self.actor
        )
        assert result is None
        assert len(RecordingHandler.requests) == 1, "the state GET is the only request"
        assert self._audit_rows() == []

    def test_performed_stop_emits_stopped(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import stop_sql_warehouse

        self._mirror_row(state="RUNNING")
        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="RUNNING")),
            "",
        ]
        assert (
            stop_sql_warehouse(self.workspace, "wh-1", client=_client(port), actor_user=self.actor)
            == {}
        )
        rows = self._audit_rows()
        assert len(rows) == 1
        assert rows[0].action == "STOPPED"

    def test_no_op_stop_emits_nothing(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import stop_sql_warehouse

        self._mirror_row(state="STOPPED")
        port = self._server()
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="STOPPED"))]
        assert (
            stop_sql_warehouse(self.workspace, "wh-1", client=_client(port), actor_user=self.actor)
            is None
        )
        assert self._audit_rows() == []

    # ── resize / delete ─────────────────────────────────────────────────

    def test_resize_emits_resized_with_the_size(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import resize_sql_warehouse

        self._mirror_row(state="STOPPED")
        port = self._server()
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(size="L", serverless=False))]
        result = resize_sql_warehouse(
            self.workspace, "wh-1", "L", client=_client(port), actor_user=self.actor
        )
        assert result["id"] == "wh-1"
        assert result["size"] == "L"
        rows = self._audit_rows()
        assert len(rows) == 1
        assert rows[0].action == "RESIZED"
        assert rows[0].details_json["size"] == "L"

    def test_delete_emits_deleted(self):
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import delete_sql_warehouse

        self._mirror_row(state="STOPPED")
        port = self._server()
        RecordingHandler.json_script = [""]
        assert (
            delete_sql_warehouse(
                self.workspace, "wh-1", client=_client(port), actor_user=self.actor
            )
            is None
        )
        rows = self._audit_rows()
        assert len(rows) == 1
        assert rows[0].action == "DELETED"

    # ── failure contracts ───────────────────────────────────────────────

    def test_state_error_propagates_without_an_audit_row(self):
        # The spec scenario: a failed state transition surfaces
        # DATABRICKS_WAREHOUSE_STATE_ERROR — the ERROR is the surface,
        # no audit row is fabricated for an operation that did not run.
        from hub.apps.databricks_admin.sql_warehouse_client import DatabricksWarehouseStateError
        from hub.apps.databricks_admin.sql_warehouse_lifecycle import start_sql_warehouse

        self._mirror_row(state="DELETING")
        port = self._server()
        RecordingHandler.json_script = [json.dumps(_warehouse_payload(state="DELETING"))]
        with pytest.raises(DatabricksWarehouseStateError) as excinfo:
            start_sql_warehouse(self.workspace, "wh-1", client=_client(port), actor_user=self.actor)
        assert excinfo.value.code == "DATABRICKS_WAREHOUSE_STATE_ERROR"
        assert len(RecordingHandler.requests) == 1, "no START is issued on DELETING"
        assert self._audit_rows() == []

    def test_audit_outage_never_blocks_the_operation(self):
        # The Phase 273 best-effort contract: an audit-DB failure must
        # never fail the lifecycle operation itself. (unittest.mock as a
        # context manager — pytest fixtures cannot serve TestCase
        # methods, the 0.8 trap.)
        from unittest import mock

        from hub.apps.databricks_admin.sql_warehouse_lifecycle import start_sql_warehouse

        self._mirror_row(state="STOPPED")

        def _explode(*_args, **_kwargs):
            raise RuntimeError("audit DB down")

        import hub.apps.audit.utils as audit_utils

        patch = mock.patch.object(audit_utils, "create_audit_event", _explode)
        patch.start()
        self.addCleanup(patch.stop)
        port = self._server()
        RecordingHandler.json_script = [
            json.dumps(_warehouse_payload(state="STOPPED")),
            "",
        ]
        # The operation completes and returns its payload; the audit
        # failure is swallowed (best-effort by contract).
        assert (
            start_sql_warehouse(self.workspace, "wh-1", client=_client(port), actor_user=self.actor)
            == {}
        )
        assert self._audit_rows() == []
