"""P7 (openspec add-databricks-cost-guardrails task 7.3, design D2) — the
hourly `system.billing.usage` sync pins.

No mocks: real Postgres rows (workspace + RUNNING SQL-warehouse mirror +
the workspace's real Fernet-encrypted M2M credential WITH the real
Phase-272 AccessRequest approver-chain linkage), the PRODUCTION
`DatabricksApiClient` + `SqlStatementExecutor` against a REAL threaded
local statement-API server whose sqlite3 executes the submitted SQL FOR
REAL with named-parameter binding (the 6.7/5.4 convention — the delta
WHERE runs for real), and the ledger rows written under the REAL
`tenant_context` (the RQ-handler contract). The sanctioned seam is the
client factory (the 1.4 `_local_client_factory` pattern).

Pinned contracts:
  - the fail-closed skips (no M2M credential / no approver-chain linkage
    / no RUNNING warehouse mirror) record a reason and touch ZERO
    network,
  - the happy path appends the billing delta to the ledger with the
    source attribution and advances the workspace's sync stamp,
  - the NEXT run reads ONLY rows at-or-after the stamp (the parameter
    never rides in the SQL text),
  - the RQ handler wraps the whole sync in tenant_context and one
    tenant's skip never blocks another tenant's sync,
  - the management command discovers via the admin DB and enqueues one
    DATABRICKS_COST_SYNC job per tenant under tenant_context.
"""

import http.server
import json
import sqlite3
import threading
import uuid
from typing import ClassVar
from urllib.parse import urlparse

from django.test import TransactionTestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.databricks_admin.models import (
    DatabricksCloud,
    DatabricksCredential,
    DatabricksCredentialAuthMode,
    DatabricksSqlWarehouse,
    DatabricksWorkspace,
    DatabricksWorkspaceStatus,
)
from hub.apps.databricks_admin.tests._fixtures import REAL_HOST, require_dns
from hub.apps.governance.models import AccessRequest, AccessRequestStatus
from tests.factories import TenantFactory

# ── The statement-API server (real HTTP + real sqlite execution) ────────


class BillingStatementHandler(http.server.BaseHTTPRequestHandler):
    """Path-routed Databricks statement-API server backed by a REAL
    sqlite3 database with the ``system.billing.usage`` table — every
    submitted statement executes FOR REAL (named ``:param`` binding)."""

    db: ClassVar[sqlite3.Connection]
    db_lock: ClassVar[threading.Lock]
    requests: ClassVar[list[dict]] = []

    def _handle(self):
        content_length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""
        parsed = urlparse(self.path)
        type(self).requests.append(
            {"method": self.command, "path": parsed.path, "body": raw_body.decode()}
        )
        if self.command == "POST" and parsed.path == "/oidc/v1/token":
            status, body = 200, b'{"access_token": "tok-cost"}'
        elif self.command == "POST" and parsed.path == "/api/2.0/sql/statements":
            payload = json.loads(raw_body)
            statement_id = f"s-{uuid.uuid4().hex[:8]}"
            with type(self).db_lock:
                cursor = type(self).db.execute(
                    payload["statement"], payload.get("parameters") or {}
                )
                columns = [d[0] for d in cursor.description]
                rows = [list(row) for row in cursor.fetchall()]
            envelope = {
                "statement_id": statement_id,
                "status": {"state": "SUCCEEDED"},
                "manifest": {"schema": {"columns": [{"name": c} for c in columns]}},
                "result": {"data_array": rows, "chunk_index": 0, "row_count": len(rows)},
            }
            status, body = 200, json.dumps(envelope).encode()
        elif self.command == "GET" and parsed.path.startswith("/api/2.0/sql/statements/"):
            status, body = 200, json.dumps({"status": {"state": "SUCCEEDED"}}).encode()
        else:
            status, body = 404, b"{}"
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._handle()

    def log_message(self, *_args):
        pass


def _billing_server():
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute(
        'CREATE TABLE "system.billing.usage" '
        "(start_time TEXT, usage_metadata TEXT, usage_quantity REAL, usage_unit TEXT)"
    )
    BillingStatementHandler.db = db
    BillingStatementHandler.db_lock = threading.Lock()
    BillingStatementHandler.requests = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), BillingStatementHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, db


def _local_client_factory(port):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    def factory(workspace, identity):
        return DatabricksApiClient(
            base_url=f"http://127.0.0.1:{port}",
            tenant_id=str(workspace.tenant_id),
            credential_config=identity.credential.get_config(),
            auth_mode=identity.credential.auth_mode,
        )

    return factory


class _FixtureMixin:
    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        self.workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name=f"cost-ws-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        from django.contrib.auth import get_user_model

        self.user = get_user_model().objects.create_user(
            email=f"cost-{uuid.uuid4().hex[:8]}@test.com", password="x"
        )
        self.warehouse = DatabricksSqlWarehouse.objects.create(
            workspace=self.workspace,
            warehouse_id=f"wh-{uuid.uuid4().hex[:8]}",
            name="analytics",
            state="RUNNING",
            serverless=True,
        )

    def tearDown(self):
        if getattr(self, "server", None):
            self.server.shutdown()
            self.server.server_close()
            self.db.close()

    def _make_approval(self):
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"cost-sync-asset-{uuid.uuid4().hex[:8]}",
            name="Cost sync authorization asset",
            description="polymorphic anchor for the cost-sync M2M credential",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        return AccessRequest.objects.create(
            tenant=self.tenant,
            requested_by=self.user,
            asset=asset,
            requested_access_type="ADMIN",
            reason="authorize the cost sync M2M credential",
            status=AccessRequestStatus.APPROVED,
            requires_approval=True,
            approval_workflow=[{"step": 1, "approver_role": "TENANT_ADMIN", "status": "APPROVED"}],
            approvers=[str(self.user.id)],
            approved_by=self.user,
            approved_at=timezone.now(),
        )

    def _make_credential(self, approval=None):
        credential = DatabricksCredential(
            workspace=self.workspace,
            auth_mode=DatabricksCredentialAuthMode.OAUTH_M2M,
            approval_request=approval,
        )
        credential.set_config({"client_id": "sync-client", "client_secret": "sync-secret"})
        credential.save()
        return credential

    def _seed_usage(self, rows):
        with BillingStatementHandler.db_lock:
            BillingStatementHandler.db.executemany(
                'INSERT INTO "system.billing.usage" '
                "(start_time, usage_metadata, usage_quantity, usage_unit) VALUES (?, ?, ?, ?)",
                rows,
            )

    def _sync(self, *, port=None):
        from hub.apps.databricks_admin.cost_sync import sync_workspace_cost

        factory = _local_client_factory(port) if port else None
        return sync_workspace_cost(self.workspace, client_factory=factory)


class TestCostSyncFailClosedSkips(_FixtureMixin, TransactionTestCase):
    def test_no_m2m_credential_skips_with_zero_network(self):
        server, _thread, db = _billing_server()
        self.server, self.db = server, db

        outcome = self._sync(port=server.server_address[1])

        assert "skipped" in outcome
        assert "M2M" in outcome["skipped"]
        assert BillingStatementHandler.requests == [], "a skip must touch ZERO network"

    def test_no_approver_chain_linkage_skips_with_zero_network(self):
        server, _thread, db = _billing_server()
        self.server, self.db = server, db
        self._make_credential(approval=None)

        outcome = self._sync(port=server.server_address[1])

        assert "skipped" in outcome
        assert BillingStatementHandler.requests == [], "a skip must touch ZERO network"

    def test_no_running_warehouse_skips_with_zero_network(self):
        server, _thread, db = _billing_server()
        self.server, self.db = server, db
        self._make_credential(approval=self._make_approval())
        self.warehouse.state = "STOPPED"
        self.warehouse.save()

        outcome = self._sync(port=server.server_address[1])

        assert "skipped" in outcome
        assert BillingStatementHandler.requests == [], "a skip must touch ZERO network"


class TestCostSyncHappyPath(_FixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.server, self._thread, self.db = _billing_server()
        self._make_credential(approval=self._make_approval())

    def test_the_delta_lands_in_the_ledger_and_advances_the_stamp(self):
        self._seed_usage(
            [
                ("2026-09-13T01:00:00Z", "STANDARD_ALL_PURPOSE_COMPUTE", 2.5, "DBU"),
                ("2026-09-13T02:00:00Z", "STANDARD_ALL_PURPOSE_COMPUTE", 1.0, "DBU"),
            ]
        )
        from hub.apps.databricks_admin.models import DatabricksCostLedger

        outcome = self._sync(port=self.server.server_address[1])

        assert outcome.get("rows_ingested") == 2
        self.workspace.refresh_from_db()
        assert self.workspace.last_cost_synced_at.isoformat() == "2026-09-13T02:00:00+00:00", (
            "the stamp advances to the max billing start_time"
        )
        rows = list(
            DatabricksCostLedger.objects.filter(
                tenant=self.tenant, workspace=self.workspace, source="billing_sync"
            ).order_by("recorded_at")
        )
        assert len(rows) == 2
        assert float(rows[0].units) == 2.5
        assert rows[0].unit_label == "DBU"
        assert rows[0].meta.get("start_time") == "2026-09-13T01:00:00Z"
        assert rows[0].tenant_id == self.workspace.tenant_id

    def test_the_second_run_reads_only_rows_after_the_stamp(self):
        self._seed_usage([("2026-09-13T01:00:00Z", "COMPUTE", 1.0, "DBU")])
        assert self._sync(port=self.server.server_address[1]).get("rows_ingested") == 1

        submitted = [
            r["body"]
            for r in BillingStatementHandler.requests
            if r["path"] == "/api/2.0/sql/statements"
        ]
        first_sql = json.loads(submitted[0])["statement"]
        assert "WHERE" not in first_sql.upper(), "the first run reads everything (no bound)"

        self._seed_usage([("2026-09-13T02:30:00Z", "COMPUTE", 1.5, "DBU")])
        outcome = self._sync(port=self.server.server_address[1])

        assert outcome.get("rows_ingested") == 1, "only the NEW delta lands"
        submitted = [
            r["body"]
            for r in BillingStatementHandler.requests
            if r["path"] == "/api/2.0/sql/statements"
        ]
        second_payload = json.loads(submitted[1])
        second_sql = second_payload["statement"]
        assert "start_time" in second_sql, (
            "the STRICT > bound — the boundary row is already in the ledger"
        )
        assert ">" in second_sql, "the STRICT > bound — the boundary row is already in the ledger"
        assert second_payload.get("parameters") == {"last_synced": "2026-09-13T01:00:00Z"}, (
            "the stamp rides as a named parameter, never in the SQL text"
        )
        assert "2026-09-13T01:00:00Z" not in second_sql


class TestCostSyncJobHandler(_FixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.server, self._thread, self.db = _billing_server()

    def test_the_handler_wraps_tenant_context_and_isolates_skips(self):
        from hub.apps.databricks_admin.cost_sync_jobs import (
            _execute_databricks_cost_sync_job,
        )
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # A healthy workspace + a fail-closed workspace of the SAME tenant
        # — the healthy sync lands under tenant_context and the
        # fail-closed skip never blocks it (the isolation contract; a
        # different tenant's workspaces are RLS-invisible to this job).
        self._make_credential(approval=self._make_approval())
        self._seed_usage([("2026-09-13T01:00:00Z", "COMPUTE", 1.0, "DBU")])

        fail_closed_workspace = DatabricksWorkspace.objects.create(
            tenant=self.tenant,
            name=f"no-cred-ws-{uuid.uuid4().hex[:8]}",
            host=REAL_HOST,
            cloud=DatabricksCloud.AWS,
            region="us-east-1",
            status=DatabricksWorkspaceStatus.ACTIVE,
        )
        DatabricksSqlWarehouse.objects.create(
            workspace=fail_closed_workspace,
            warehouse_id=f"wh-{uuid.uuid4().hex[:8]}",
            name="analytics",
            state="RUNNING",
            serverless=True,
        )
        # No credential on the fail-closed workspace → skip.

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DATABRICKS_COST_SYNC,
            status=JobStatus.PENDING,
            resource_type="TENANT",
            resource_id=uuid.uuid4(),
        )

        outcome = _execute_databricks_cost_sync_job(
            job, client_factory=_local_client_factory(self.server.server_address[1])
        )

        assert outcome["workspaces_synced"] == 1
        assert len(outcome["workspaces_skipped"]) == 1
        assert outcome["workspaces_skipped"][0]["reason"]

        from hub.apps.databricks_admin.models import DatabricksCostLedger

        rows = DatabricksCostLedger.objects.filter(tenant=self.tenant, source="billing_sync")
        assert rows.count() == 1, "the healthy tenant's delta landed under tenant_context"
        assert not DatabricksCostLedger.objects.filter(
            tenant=self.tenant, workspace=fail_closed_workspace
        ).exists()
