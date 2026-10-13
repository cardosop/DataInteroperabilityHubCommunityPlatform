"""Journey pins for the P6 Databricks DLT movement surface (openspec
wire-databricks-dlt-movement task 6.10) — JOURNEY-DB-013 (Export a
Dataset to Databricks) + UC-DB-013 (Export Dataset to Databricks);
JOURNEY-DB-014 (Ingest from a Databricks Source) + UC-DB-014 (Ingest
from Databricks).

Class/method names are PINNED by the UC docs' "Phase P6 Test" fields
(docs/mvpdocs/use-cases/UC-DB-013.md / UC-DB-014.md) — renaming them
breaks the docs↔test drift gates (GATE-28).

The journeys span the shipped P6 surfaces with NO mocks — real Postgres
rows (tenant/connection/export/run/audit), the REAL movement spines
(``execute_dlt_export`` through the real trigger dispatch — the ODCS
preflight, the managed-volume staging resolution, the scoped write
credential, the guard-bypass executor scope; ``execute_dlt_ingestion``'s
DATABRICKS_SOURCE branch — the REAL ``WarehouseQueryRunner`` read over a
real threaded statement-API server whose sqlite executes the SQL FOR
REAL, the real dlt load into a real bucket, the incremental cursor in
the real dlt state). The sanctioned seams are the connector-factory
symbol (a REAL ``WarehouseConnector`` subclass — the 6.3/6.7 recording
convention), the recording pipeline + credential resolver (the 6.5
export convention), and the retry-sleeper constants.
"""

from __future__ import annotations

import http.server
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from unittest import mock

import pytest
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

from hub.data_movement.tests.test_dlt_incremental import (
    RecordingStatementConnector,
    StatementApiHandler,
    _make_client,
    _mk_ingestion,
    _read_bucket_rows,
    _seed,
)

# ── shared helpers ────────────────────────────────────────────────────────

DATABRICKS_DEST = {
    "host": "dbc-abc.cloud.databricks.com",
    "http_path": "/sql/1.0/warehouses/abc123",
    "catalog": "meshant",
    "schema": "staging",
}


def _mk_tenant(*, flagged=True):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"jrn-{uid}",
        slug=f"jrn-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=flagged,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"jrn-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_connection(tenant, *, config=None):
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

    return WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uuid.uuid4().hex[:8]}",
        warehouse_type=WarehouseType.DATABRICKS,
        config=config
        or {
            "host": "adb-src.azuredatabricks.net",
            "auth_mode": "PAT",
            "pat_token": "dapi-src",
        },
    )


def _mk_export(tenant, *, source_scope=None, credential_ref=None):
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"exp-{uuid.uuid4().hex[:8]}",
        destination_type="DATABRICKS_TABLE",
        destination_config=DATABRICKS_DEST,
        # The model's clean() requires a non-empty scope with at least
        # one key — file ids carry no contract checks, so the preflight
        # passes while the scope stays valid.
        source_scope=source_scope
        if source_scope is not None
        else {"file_ids": [str(uuid.uuid4())]},
        schedule_config={"cron": "0 3 * * *"},
        credential_ref=credential_ref,
    )


def _mk_contract(tenant, asset, *, validation_status="VALID"):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        status="ACTIVE",
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="JSON",
        original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
        validation_status=validation_status,
    )


class _RecordingPipeline:
    """A REAL minimal pipeline at the sanctioned factory symbol — its
    run() proves the guard-bypass contract from INSIDE the run (the
    pipeline execution context; the 6.5 convention)."""

    def __init__(self):
        self.run_calls = 0
        self.run_kwargs: list[dict] = []

    def run(self, **kwargs):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        self.run_calls += 1
        self.run_kwargs.append(kwargs)
        ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")
        return {"loads": [{"load_id": "l1", "status": "completed"}]}


@contextmanager
def _statement_server():
    """A real threaded statement-API server over a real in-memory sqlite
    database with the ``source_rows`` table (the 6.7 convention)."""
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.execute("CREATE TABLE source_rows (id INTEGER PRIMARY KEY, name TEXT, updated_at TEXT)")
    StatementApiHandler.db = db
    StatementApiHandler.db_lock = threading.Lock()
    StatementApiHandler.statements = {}
    StatementApiHandler.requests = []
    StatementApiHandler.forced_state = None
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), StatementApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address[1]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        db.close()


@pytest.fixture
def journey_statement_server():
    with _statement_server() as port:
        yield port


# ── JOURNEY-DB-013 — Export a Dataset to Databricks ───────────────────────


@pytest.mark.journey("JOURNEY-DB-013")
@pytest.mark.uc("UC-DB-013")
class TestJOURNEYDB013ExportDatasetToDatabricks(TestCase):
    """The doc-pinned class (UC-DB-013's Phase P6 Test) — the export
    journey's spine: trigger → preflight → staging + scoped credential →
    the pipeline run inside the guard-bypass scope → the terminal run
    state + the audit trail."""

    def setUp(self):
        self.tenant = _mk_tenant()
        self.user = _mk_user(self.tenant)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def _patched_spine(self):
        from hub.data_movement import export_execution

        pipeline = _RecordingPipeline()
        creds_calls: list = []

        def pipeline_factory(**kwargs):
            assert set(kwargs) == {"destination_type", "pipeline_name", "credential_ref"}
            return pipeline

        def creds_resolver(credential_ref=None):
            creds_calls.append(credential_ref)
            return {"token": "dapi-export-token"}

        return (
            mock.patch.multiple(
                export_execution,
                create_export_pipeline=pipeline_factory,
                resolve_credentials=creds_resolver,
            ),
            pipeline,
            creds_calls,
        )

    def test_export_spine(self):
        """The doc-pinned method — the export journey's end-to-end walk:
        the real trigger dispatches the REAL spine; the preflight passes;
        the staging target + scoped write credential resolve from the
        destination config; the pipeline runs INSIDE the guard-bypass
        scope (proven from inside the run); the run's terminal state
        records the outcome; STARTED + COMPLETED audit rows exist."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.scheduled_export.models import (
            ScheduledExportRun,
            ScheduledExportRunStatus,
        )

        # A credential_ref so the spine consults the (patched) resolver —
        # the entrypoint short-circuits creds to {} when the ref is falsy.
        scheduled_export = _mk_export(self.tenant, credential_ref="test-ref")
        patches, pipeline, _creds_calls = self._patched_spine()
        with patches:
            resp = self.client.post(
                f"/api/v1/scheduled-exports/{scheduled_export.id}/trigger/",
                data={},
                format="json",
            )

        assert resp.status_code == 200
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.COMPLETED, (
            "the run's terminal state records the movement outcome"
        )
        assert pipeline.run_calls == 1, "the pipeline ran exactly once, inside the scope"
        assert (run.result_json or {}).get("dlt_outcome", {}).get("items_exported") == 1
        assert AuditEvent.objects.filter(
            tenant=self.tenant, action="WAREHOUSE_EXPORT_STARTED"
        ).exists(), "one STARTED row at the dispatch chokepoint"
        assert AuditEvent.objects.filter(
            tenant=self.tenant, action="DLT_EXPORT_COMPLETED", result="SUCCESS"
        ).exists(), "the terminal audit row records the success"

    def test_an_invalid_contract_refuses_before_any_work(self):
        """The ODCS preflight: an INVALID contract refuses the run with
        ZERO side effects — no STARTED row, no pipeline run."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.scheduled_export.models import (
            ScheduledExportRun,
            ScheduledExportRunStatus,
        )
        from tests.factories import AssetFactory

        asset = AssetFactory.create(tenant=self.tenant)
        _mk_contract(self.tenant, asset, validation_status="INVALID")
        scheduled_export = _mk_export(self.tenant, source_scope={"asset_ids": [str(asset.id)]})
        patches, pipeline, _creds_calls = self._patched_spine()
        with patches:
            resp = self.client.post(
                f"/api/v1/scheduled-exports/{scheduled_export.id}/trigger/",
                data={},
                format="json",
            )

        assert resp.status_code == 200
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.FAILED
        assert pipeline.run_calls == 0, "the refusal happens BEFORE any pipeline work"
        assert AuditEvent.objects.filter(
            tenant=self.tenant, action="WAREHOUSE_EXPORT_FAILED"
        ).exists(), "the FAILED terminal row carries the classified refusal"
        assert not AuditEvent.objects.filter(
            tenant=self.tenant, action="WAREHOUSE_EXPORT_STARTED"
        ).exists(), "a refused run never dispatches — no STARTED row"

    def test_a_databricks_export_without_a_scoped_credential_fails_closed(self):
        """The credential gate: no token-shaped material → the run fails
        closed with the classified refusal — zero pipeline work."""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.scheduled_export.models import (
            ScheduledExportRun,
            ScheduledExportRunStatus,
        )
        from hub.data_movement import export_execution

        scheduled_export = _mk_export(self.tenant)
        pipeline = _RecordingPipeline()

        def pipeline_factory(**kwargs):
            return pipeline

        with mock.patch.multiple(
            export_execution,
            create_export_pipeline=pipeline_factory,
            resolve_credentials=lambda credential_ref=None: {},
        ):
            resp = self.client.post(
                f"/api/v1/scheduled-exports/{scheduled_export.id}/trigger/",
                data={},
                format="json",
            )

        assert resp.status_code == 200
        run = ScheduledExportRun.objects.get(scheduled_export=scheduled_export)
        assert run.status == ScheduledExportRunStatus.FAILED
        assert pipeline.run_calls == 0
        assert AuditEvent.objects.filter(
            tenant=self.tenant, action="WAREHOUSE_EXPORT_FAILED"
        ).exists()

    def test_the_read_side_delegates_through_the_real_runner(self):
        """The export journey's data leg: the REAL WarehouseQueryRunner
        bound to the connection's own encrypted config reads through the
        production connector factory (the sanctioned recording connector
        over the real statement server — real transport, real SQL
        execution)."""
        from hub.data_movement import warehouse_query_runner as runner_module
        from hub.data_movement.warehouse_query_runner import WarehouseQueryRunner

        connection = _mk_connection(self.tenant)
        RecordingStatementConnector.script = []
        with _statement_server() as port:
            _seed([(1, "a", "2026-01-01T00:00:00Z"), (2, "b", "2026-01-02T00:00:00Z")])
            RecordingStatementConnector.client = _make_client(port)

            def factory(_warehouse_type):
                return RecordingStatementConnector

            with mock.patch.object(runner_module, "get_connector_for_connection", factory):
                runner = WarehouseQueryRunner.from_connection(connection, query_type="export")
                rows = runner.execute('SELECT * FROM source_rows ORDER BY "updated_at"')

        assert [row["id"] for row in rows] == [1, 2], "the read returns the real rows"
        assert RecordingStatementConnector.script[0]["statement"].startswith(
            "SELECT * FROM source_rows"
        )


# ── JOURNEY-DB-014 — Ingest from a Databricks Source ──────────────────────


@pytest.mark.journey("JOURNEY-DB-014")
@pytest.mark.uc("UC-DB-014")
class TestJOURNEYDB014IngestFromDatabricksSource:
    """The doc-pinned class (UC-DB-014's Phase P6 Test) — the ingestion
    journey: the REAL DATABRICKS_SOURCE branch reads through the runner
    (bounded by the incremental cursor), loads through the dlt resource,
    and advances the cursor only after a successful load."""

    def _stack(self, monkeypatch, tmp_path, journey_statement_server):
        from django.conf import settings

        from hub.data_movement import warehouse_query_runner as runner_module

        # W3.8 — a successful read materializes File/Dataset rows: the
        # S3 storage boundary stand-in + ClamAV disabled (the
        # SCAN_UNAVAILABLE branch — no scan-enqueue dependency).
        monkeypatch.setattr(settings, "CLAMAV_ENABLED", False)
        monkeypatch.setattr(
            "hub.apps.files.storage.S3StorageClient.save_file",
            lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: (
                f"{tenant_id}/{file_id}/content"
            ),
        )

        tenant = _mk_tenant()
        connection = _mk_connection(tenant)
        RecordingStatementConnector.script = []
        RecordingStatementConnector.client = _make_client(journey_statement_server)

        def factory(_warehouse_type):
            return RecordingStatementConnector

        monkeypatch.setattr(runner_module, "get_connector_for_connection", factory)
        monkeypatch.setattr(runner_module.WarehouseQueryRunner, "_RETRY_DELAYS", [0, 0, 0])
        import dlt

        monkeypatch.setitem(dlt.config, "pipelines.pipelines_dir", str(tmp_path / "pipelines"))
        bucket = tmp_path / "bucket"
        monkeypatch.setenv("DESTINATION__FILESYSTEM__BUCKET_URL", f"file://{bucket}")
        return tenant, connection, str(bucket)

    def test_ingestion_spine(self, monkeypatch, tmp_path, journey_statement_server):
        """The doc-pinned method — the first run reads EVERYTHING, loads
        the rows into the real bucket, records the incremental cursor,
        and emits the ingestion audit row."""
        from hub.apps.audit.models import AuditEvent
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        tenant, connection, bucket = self._stack(monkeypatch, tmp_path, journey_statement_server)
        _seed(
            [
                (1, "a", "2026-01-01T00:00:00Z"),
                (2, "b", "2026-01-02T00:00:00Z"),
                (3, "c", "2026-01-03T00:00:00Z"),
            ]
        )
        ingestion = _mk_ingestion(tenant, connection)

        outcome = execute_dlt_ingestion(str(ingestion.id))

        assert outcome["error_message"] is None, outcome["error_message"]
        assert outcome["files_processed"] >= 1
        loaded = _read_bucket_rows(bucket)
        ids = sorted(row["id"] for row in loaded if "id" in row)
        assert ids == [1, 2, 3], "the first run materializes every row"
        cursor = get_databricks_source_cursor(f"ingestion-{ingestion.id}", str(ingestion.id))
        assert cursor is not None
        assert cursor["last_value"] == "2026-01-03T00:00:00Z"
        assert AuditEvent.objects.filter(
            tenant=tenant, action="DLT_INGESTION_COMPLETED", result="SUCCESS"
        ).exists(), "the ingestion audit row records the success"

    def test_the_rerun_resumes_from_the_last_cursor(
        self, monkeypatch, tmp_path, journey_statement_server
    ):
        """The spec scenario: a re-run reads ONLY the rows after the
        cursor — never a full re-read."""
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        tenant, connection, bucket = self._stack(monkeypatch, tmp_path, journey_statement_server)
        _seed(
            [
                (1, "a", "2026-01-01T00:00:00Z"),
                (2, "b", "2026-01-02T00:00:00Z"),
                (3, "c", "2026-01-03T00:00:00Z"),
            ]
        )
        ingestion = _mk_ingestion(tenant, connection)
        assert execute_dlt_ingestion(str(ingestion.id))["error_message"] is None

        _seed(
            [
                (1, "a", "2026-01-01T00:00:00Z"),
                (2, "b", "2026-01-02T00:00:00Z"),
                (3, "c", "2026-01-03T00:00:00Z"),
                (4, "d", "2026-01-04T00:00:00Z"),
            ]
        )
        assert execute_dlt_ingestion(str(ingestion.id))["error_message"] is None

        assert len(RecordingStatementConnector.script) == 2
        second = RecordingStatementConnector.script[1]
        assert '"updated_at" > :last_cursor' in second["statement"], (
            "the re-run's read is bounded by the recorded cursor"
        )
        assert second["parameters"] == {"last_cursor": "2026-01-03T00:00:00Z"}
        ids = sorted(row["id"] for row in _read_bucket_rows(bucket) if "id" in row)
        assert ids == [1, 2, 3, 4], "run 1 read everything; run 2 read ONLY the new row"

    def test_a_connectionless_source_fails_closed(
        self, monkeypatch, tmp_path, journey_statement_server
    ):
        """A DATABRICKS_SOURCE without a warehouse connection fails the
        run closed — zero HTTP against the warehouse."""
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        tenant, connection, _bucket = self._stack(monkeypatch, tmp_path, journey_statement_server)
        ingestion = _mk_ingestion(tenant, connection)
        ScheduledIngestion.objects.filter(id=ingestion.id).update(source_config={})
        submits_before = len(
            [r for r in StatementApiHandler.requests if r["path"] == "/api/2.0/sql/statements"]
        )
        outcome = execute_dlt_ingestion(str(ingestion.id))
        submits_after = len(
            [r for r in StatementApiHandler.requests if r["path"] == "/api/2.0/sql/statements"]
        )
        assert outcome["error_message"], "the run fails closed"
        assert submits_after == submits_before, "zero HTTP — refused before any read"
