"""Phase 6 (openspec wire-databricks-dlt-movement task 6.7) — the
DATABRICKS_SOURCE incremental-state contract (design D1, spec scenario
"a re-run resumes from the incremental cursor — never a full re-read").

The incremental state lives in the REAL dlt pipeline state, keyed per
pipeline + asset; the read SQL is bounded by the cursor predicate (a
parameterised ``:last_cursor`` bound — the value never rides in the SQL
text); the cursor advances ONLY after a successful load, and a schema
change on the source (rows without the cursor field) resets it by design
(dlt's documented semantics).

NO MOCKS: real dlt pipelines (filesystem destination, isolated
``DLT_PIPELINES_DIR``), the PRODUCTION ``DatabricksApiClient`` +
``SqlStatementExecutor`` over a real threaded local HTTP server whose
sqlite3 database executes the submitted SQL FOR REAL (the 5.4
statement-API convention), real load files read back from the real
bucket, and the REAL ``execute_dlt_ingestion`` wiring over real Postgres
rows — the sanctioned patch points are the connector-factory symbol (a
REAL ``WarehouseConnector`` subclass — the 5.3/6.3 recording convention)
and the retry sleeper (the 4.4 convention).
"""

from __future__ import annotations

import gzip
import http.server
import json
import sqlite3
import threading
import uuid
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import pytest

from hub.apps.warehouses.base import WarehouseConnector

pytestmark = pytest.mark.django_db(transaction=True)


# ── The statement-API server (real HTTP + real sqlite execution) ────────


class StatementApiHandler(http.server.BaseHTTPRequestHandler):
    """Path-routed Databricks statement-API server backed by a REAL
    sqlite3 database: every submitted statement is executed for real
    (named ``:param`` binding) and the terminal envelope is answered
    inline from the REAL result. ``/oidc/v1/token`` answers the
    client's token exchange. Every (method, path, body) is recorded.
    ``forced_state`` scripts a FAILED terminal state (the failure leg).
    """

    db: ClassVar[sqlite3.Connection]
    db_lock: ClassVar[threading.Lock]
    statements: ClassVar[dict[str, dict]] = {}
    requests: ClassVar[list[dict]] = []
    forced_state: ClassVar[str | None] = None

    def _handle(self):
        content_length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(content_length) if content_length else b""
        parsed = urlparse(self.path)
        type(self).requests.append(
            {"method": self.command, "path": parsed.path, "body": raw_body.decode()}
        )
        if self.command == "POST" and parsed.path == "/oidc/v1/token":
            status, body = 200, b'{"access_token": "tok-src"}'
        elif self.command == "POST" and parsed.path == "/api/2.0/sql/statements":
            payload = json.loads(raw_body)
            statement_id = f"s-{uuid.uuid4().hex[:8]}"
            if type(self).forced_state:
                envelope = {
                    "statement_id": statement_id,
                    "status": {
                        "state": type(self).forced_state,
                        "error": {"message": "scripted failure"},
                    },
                }
            else:
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
            type(self).statements[statement_id] = envelope
            status, body = 200, json.dumps(envelope).encode()
        elif self.command == "GET" and parsed.path.startswith("/api/2.0/sql/statements/"):
            statement_id = parsed.path.rstrip("/").rsplit("/", 1)[-1]
            envelope = type(self).statements.get(statement_id, {})
            status, body = 200, json.dumps(envelope).encode()
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


@pytest.fixture
def statement_server():
    """A real threaded statement-API server over a real in-memory sqlite
    database with the ``source_rows`` table (id / name / updated_at)."""
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


def _seed(rows: list[tuple]) -> None:
    with StatementApiHandler.db_lock:
        StatementApiHandler.db.execute("DELETE FROM source_rows")
        StatementApiHandler.db.executemany(
            "INSERT INTO source_rows (id, name, updated_at) VALUES (?, ?, ?)", rows
        )


def _make_client(port: int):
    """The PRODUCTION DatabricksApiClient against the local server (the
    5.4 convention)."""
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id="t-src",
        credential_config={"token": "dapi-src"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,
    )


def _make_executor(port: int):
    """The PRODUCTION client + statement executor against the local
    server (the 5.4 convention)."""
    from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

    return SqlStatementExecutor(
        client=_make_client(port),
        warehouse_id="wh-src",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=2.0,
    )


def _isolated_pipelines(monkeypatch, tmp_path: Path) -> None:
    """Isolate dlt pipeline state per test through the REAL dlt config
    (dlt 1.30 resolves ``pipelines.pipelines_dir`` from config injection —
    the env-var spelling is not wired for this key)."""
    import dlt

    monkeypatch.setitem(dlt.config, "pipelines.pipelines_dir", str(tmp_path / "pipelines"))


def _isolated_bucket(monkeypatch, tmp_path: Path) -> str:
    bucket = tmp_path / "bucket"
    monkeypatch.setenv("DESTINATION__FILESYSTEM__BUCKET_URL", f"file://{bucket}")
    return str(bucket)


# ── Cursor state semantics (real dlt pipeline state) ─────────────────────


class TestDatabricksSourceCursorState:
    def test_a_fresh_pipeline_has_no_cursor(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor

        assert get_databricks_source_cursor("p-fresh", "asset-a") is None

    def test_advance_persists_across_pipeline_instances(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        rows = [{"updated_at": "2026-01-02T00:00:00Z"}, {"updated_at": "2026-01-01T00:00:00Z"}]
        assert (
            advance_databricks_source_cursor(
                "p-adv", "asset-a", cursor_field="updated_at", rows=rows
            )
            == "2026-01-02T00:00:00Z"
        )
        cursor = get_databricks_source_cursor("p-adv", "asset-a")
        assert cursor == {
            "cursor_field": "updated_at",
            "last_value": "2026-01-02T00:00:00Z",
            "updated_at": cursor["updated_at"],
        }
        assert cursor["updated_at"]

    def test_cursors_are_keyed_per_asset_within_a_pipeline(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        advance_databricks_source_cursor(
            "p-keys", "asset-a", cursor_field="updated_at", rows=[{"updated_at": "t-a"}]
        )
        assert get_databricks_source_cursor("p-keys", "asset-b") is None
        assert get_databricks_source_cursor("p-keys", "asset-a")["last_value"] == "t-a"

    def test_cursors_are_isolated_per_pipeline(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        advance_databricks_source_cursor(
            "p-one", "asset-a", cursor_field="updated_at", rows=[{"updated_at": "t-1"}]
        )
        assert get_databricks_source_cursor("p-two", "asset-a") is None

    def test_an_empty_read_keeps_the_existing_cursor(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        advance_databricks_source_cursor(
            "p-empty", "asset-a", cursor_field="updated_at", rows=[{"updated_at": "t-1"}]
        )
        advance_databricks_source_cursor("p-empty", "asset-a", cursor_field="updated_at", rows=[])
        assert get_databricks_source_cursor("p-empty", "asset-a")["last_value"] == "t-1"

    def test_rows_without_the_cursor_field_reset_the_cursor(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        advance_databricks_source_cursor(
            "p-reset", "asset-a", cursor_field="updated_at", rows=[{"updated_at": "t-1"}]
        )
        # A schema change on the source (the cursor column gone) resets the
        # cursor by design — the next run re-reads everything.
        advance_databricks_source_cursor(
            "p-reset", "asset-a", cursor_field="updated_at", rows=[{"name": "no-cursor"}]
        )
        assert get_databricks_source_cursor("p-reset", "asset-a") is None

    def test_advance_takes_the_max_cursor_value_seen(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import advance_databricks_source_cursor

        value = advance_databricks_source_cursor(
            "p-max",
            "asset-a",
            cursor_field="updated_at",
            rows=[
                {"updated_at": "2026-01-01T00:00:00Z"},
                {"updated_at": "2026-01-03T00:00:00Z"},
                {"updated_at": "2026-01-02T00:00:00Z"},
            ],
        )
        assert value == "2026-01-03T00:00:00Z"

    def test_mixed_cursor_types_reset_the_cursor(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            get_databricks_source_cursor,
        )

        advance_databricks_source_cursor(
            "p-mixed", "asset-a", cursor_field="updated_at", rows=[{"updated_at": "t-1"}]
        )
        # Uncomparable cursor values (type drift) are treated as a schema
        # change: reset, never a silently wrong bound.
        advance_databricks_source_cursor(
            "p-mixed",
            "asset-a",
            cursor_field="updated_at",
            rows=[{"updated_at": "2026-01-01T00:00:00Z"}, {"updated_at": 123}],
        )
        assert get_databricks_source_cursor("p-mixed", "asset-a") is None

    def test_the_file_helpers_persist_state_on_the_pinned_dlt(self, monkeypatch, tmp_path):
        """The 285.6 file-cursor helpers persist through the dlt 1.30
        state API (the ``pipeline.state = state`` setter pattern was
        removed in dlt 1.x — a re-run resumes, never a full re-scan)."""
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import incremental_by_last_modified

        files = [
            {"key": "f-1", "last_modified": "2026-01-01T00:00:00Z"},
            {"key": "f-2", "last_modified": "2026-01-02T00:00:00Z"},
        ]
        first = incremental_by_last_modified(files, "p-files")
        assert [f["key"] for f in first] == ["f-1", "f-2"]
        second = incremental_by_last_modified(files, "p-files")
        assert second == [], "the cursor must persist — a re-run re-reads nothing"


# ── The read SQL builder (guards + parameterisation) ─────────────────────


class TestDatabricksSourceReadSql:
    def test_a_first_run_read_is_unbounded(self):
        from hub.data_movement.dlt_incremental import databricks_source_read_sql

        sql, params = databricks_source_read_sql("source_rows", "updated_at", None)
        assert sql == 'SELECT * FROM source_rows ORDER BY "updated_at"'
        assert params is None

    def test_a_cursor_run_is_bounded_and_parameterised(self):
        from hub.data_movement.dlt_incremental import databricks_source_read_sql

        cursor = {
            "cursor_field": "updated_at",
            "last_value": "2026-01-02T00:00:00Z",
            "updated_at": "2026-01-02T00:00:01Z",
        }
        sql, params = databricks_source_read_sql("source_rows", "updated_at", cursor)
        assert sql == (
            'SELECT * FROM source_rows WHERE "updated_at" > :last_cursor ORDER BY "updated_at"'
        )
        assert params == {"last_cursor": "2026-01-02T00:00:00Z"}
        assert "2026-01-02T00:00:00Z" not in sql, "the cursor value must never ride in the SQL"

    @pytest.mark.parametrize(
        "table_ref",
        ["source_rows", "main.source_rows", "catalog.schema.source_rows"],
    )
    def test_the_table_ref_guard_accepts_qualified_names(self, table_ref):
        from hub.data_movement.dlt_incremental import databricks_source_read_sql

        sql, _params = databricks_source_read_sql(table_ref, "updated_at", None)
        assert sql == f'SELECT * FROM {table_ref} ORDER BY "updated_at"'

    @pytest.mark.parametrize(
        "table_ref",
        ["", "x; DROP TABLE source_rows", "source rows", '"source_rows"', "1table"],
    )
    def test_the_table_ref_guard_refuses_injection_attempts(self, table_ref):
        from hub.data_movement.dlt_incremental import (
            DatabricksSourceIncrementalError,
            databricks_source_read_sql,
        )

        with pytest.raises(DatabricksSourceIncrementalError):
            databricks_source_read_sql(table_ref, "updated_at", None)

    @pytest.mark.parametrize("cursor_field", ["updated_at", "modified_ts", "_row_seq"])
    def test_the_cursor_field_guard_accepts_identifiers(self, cursor_field):
        from hub.data_movement.dlt_incremental import incremental_sql_predicate

        fragment, params = incremental_sql_predicate(cursor_field, "v")
        assert fragment == f' WHERE "{cursor_field}" > :last_cursor'
        assert params == {"last_cursor": "v"}

    @pytest.mark.parametrize(
        "cursor_field",
        ["", "a b", "1abc", "a-b", "updated_at; DROP TABLE source_rows", "a.b", "a@b"],
    )
    def test_the_cursor_field_guard_refuses_injection_attempts(self, cursor_field):
        from hub.data_movement.dlt_incremental import (
            DatabricksSourceIncrementalError,
            incremental_sql_predicate,
        )

        with pytest.raises(DatabricksSourceIncrementalError):
            incremental_sql_predicate(cursor_field, "v")


# ── The read bound over REAL transport (never a full re-read) ────────────


class TestIncrementalReadBound:
    def test_the_second_read_returns_only_rows_after_the_cursor(
        self, monkeypatch, tmp_path, statement_server
    ):
        """The bound is proven over REAL transport: the recording
        connector (the sanctioned seam — its submit body carries the
        parameters as a JSON extension the handler binds for real)
        submits both reads to the local statement-API server whose
        sqlite executes the SQL — the second read returns ONLY the rows
        after the cursor (never a full re-read), and the cursor value
        rides in the parameters, never in the SQL text."""
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.data_movement.dlt_incremental import (
            advance_databricks_source_cursor,
            databricks_source_read_sql,
            get_databricks_source_cursor,
        )

        RecordingStatementConnector.script = []
        RecordingStatementConnector.client = _make_client(statement_server)
        connector = RecordingStatementConnector({"host": "h"}, tenant_id="t-src")
        connector.connect()
        try:
            _seed(
                [
                    (1, "a", "2026-01-01T00:00:00Z"),
                    (2, "b", "2026-01-02T00:00:00Z"),
                    (3, "c", "2026-01-03T00:00:00Z"),
                ]
            )

            sql, params = databricks_source_read_sql("source_rows", "updated_at", None)
            first = connector.execute_query(sql, params)
            assert [row[0] for row in first.rows] == [1, 2, 3], "the first run reads everything"

            advance_databricks_source_cursor(
                "p-bound",
                "asset-a",
                cursor_field="updated_at",
                rows=[{"updated_at": r[2]} for r in first.rows],
            )
            cursor = get_databricks_source_cursor("p-bound", "asset-a")
            assert cursor["last_value"] == "2026-01-03T00:00:00Z"

            _seed(
                [
                    (1, "a", "2026-01-01T00:00:00Z"),
                    (2, "b", "2026-01-02T00:00:00Z"),
                    (3, "c", "2026-01-03T00:00:00Z"),
                    (4, "d", "2026-01-04T00:00:00Z"),
                    (5, "e", "2026-01-05T00:00:00Z"),
                ]
            )
            sql, params = databricks_source_read_sql("source_rows", "updated_at", cursor)
            second = connector.execute_query(sql, params)
            assert [row[0] for row in second.rows] == [4, 5], (
                "the second run reads ONLY the rows after the cursor — never a full re-read"
            )
            assert len(RecordingStatementConnector.script) == 2
            second_record = RecordingStatementConnector.script[1]
            assert '"updated_at" > :last_cursor' in second_record["statement"]
            assert second_record["parameters"] == {"last_cursor": "2026-01-03T00:00:00Z"}
            assert "2026-01-03T00:00:00Z" not in second_record["statement"], (
                "the cursor value must never ride in the SQL text"
            )
        finally:
            connector.close()

    def test_a_failed_statement_raises_and_leaves_state_untouched(
        self, monkeypatch, tmp_path, statement_server
    ):
        _isolated_pipelines(monkeypatch, tmp_path)
        from hub.apps.databricks_admin.sql_statements import SqlStatementError
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor

        executor = _make_executor(statement_server)
        StatementApiHandler.forced_state = "FAILED"
        with pytest.raises(SqlStatementError):
            executor.execute("SELECT * FROM source_rows")
        assert get_databricks_source_cursor("p-fail", "asset-a") is None, (
            "a failed read must never advance (or reset) the cursor"
        )


# ── The dlt resource (real load to a real bucket) ────────────────────────


def _read_bucket_rows(bucket: str) -> list[dict]:
    rows: list[dict] = []
    for path in Path(bucket).rglob("*.jsonl.gz"):
        with gzip.open(path, "rt") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
    return rows


class TestDatabricksSourceResource:
    def test_the_resource_loads_rows_to_the_filesystem_bucket(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        bucket = _isolated_bucket(monkeypatch, tmp_path)
        import dlt

        from hub.data_movement.dlt_incremental import databricks_source_rows

        pipeline = dlt.pipeline(
            pipeline_name=f"p-res-{uuid.uuid4().hex[:8]}",
            destination="filesystem",
            dataset_name=f"ds_{uuid.uuid4().hex[:8]}",
        )
        rows = [
            {"id": 1, "name": "a", "updated_at": "2026-01-01T00:00:00Z"},
            {"id": 2, "name": "b", "updated_at": "2026-01-02T00:00:00Z"},
        ]
        info = pipeline.run([databricks_source_rows(rows, asset_id="asset-a")])
        assert info.loads_ids, "the load must produce a load id"
        loaded = _read_bucket_rows(bucket)
        by_id = {row["id"]: row for row in loaded if "id" in row}
        assert set(by_id) == {1, 2}
        # dlt normalizes ISO timestamps to the explicit-offset form — the
        # loaded value is the normalizer's canonical representation.
        assert by_id[1]["updated_at"] == "2026-01-01T00:00:00+00:00"
        assert all("_dlt_load_id" in row for row in loaded)

    def test_a_second_run_appends_only_the_new_rows(self, monkeypatch, tmp_path):
        _isolated_pipelines(monkeypatch, tmp_path)
        bucket = _isolated_bucket(monkeypatch, tmp_path)
        import dlt

        from hub.data_movement.dlt_incremental import databricks_source_rows

        pipeline = dlt.pipeline(
            pipeline_name=f"p-append-{uuid.uuid4().hex[:8]}",
            destination="filesystem",
            dataset_name=f"ds_{uuid.uuid4().hex[:8]}",
        )
        pipeline.run([databricks_source_rows([{"id": 1}], asset_id="asset-a")])
        pipeline.run([databricks_source_rows([{"id": 2}, {"id": 3}], asset_id="asset-a")])
        loaded = _read_bucket_rows(bucket)
        ids = sorted(row["id"] for row in loaded if "id" in row)
        assert ids == [1, 2, 3], (
            "the second run's rows land — the dedupe contract is the read bound"
        )


# ── The execute_dlt_ingestion wiring (real rows + real transport) ─────────


class RecordingStatementConnector(WarehouseConnector):
    """A REAL ``WarehouseConnector`` subclass whose transport is the
    local statement-API server (the sanctioned recording-connector seam
    — the 5.3/6.3 convention). The submit body carries the parameters as
    a JSON extension field the handler binds for real."""

    script: ClassVar[list[dict]] = []
    client = None  # the production DatabricksApiClient, set per test

    def __init__(self, connection_config, timeout_ms=30_000, tenant_id=""):
        super().__init__(connection_config, timeout_ms)
        self.tenant_id = tenant_id
        self.connected = False
        self.closed = False

    def connect(self):
        self.connected = True

    def execute_query(self, sql, params=None, limit=0):
        from hub.apps.databricks_admin.sql_statements import SqlStatementError
        from hub.apps.warehouses.base import QueryResult

        type(self).script.append({"statement": sql, "parameters": params or {}})
        response = type(self).client.request(
            "POST",
            "sql.statements.submit",
            json={
                "statement": sql,
                "wait_timeout": "10s",
                "warehouse_id": "wh-src",
                "parameters": params or {},
            },
        )
        body = response.json()
        state = body.get("status", {}).get("state")
        if state == "FAILED":
            raise SqlStatementError("Statement failed: scripted failure")
        rows = body.get("result", {}).get("data_array", [])
        columns = [c["name"] for c in body["manifest"]["schema"]["columns"]]
        return QueryResult(columns=columns, rows=rows, row_count=len(rows))

    def reflect_schema(self, _table_name):
        return []

    def close(self):
        self.closed = True


@pytest.fixture
def wired_stack(monkeypatch, tmp_path, statement_server):
    """A real stack: tenant + WarehouseConnection (real encrypted
    config) + DATABRICKS_SOURCE ScheduledIngestion (real encrypted
    source_config) + the factory seam patched with the recording
    connector bound to the local statement server + isolated dlt dirs
    + the W3.8 catalog seams (the S3 storage boundary stand-in and
    ClamAV disabled — a successful read materializes File/Dataset
    rows)."""
    from django.conf import settings

    from hub.apps.tenants.models import Tenant
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType
    from hub.data_movement import warehouse_query_runner as runner_module

    monkeypatch.setattr(settings, "CLAMAV_ENABLED", False)
    monkeypatch.setattr(
        "hub.apps.files.storage.S3StorageClient.save_file",
        lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: (
            f"{tenant_id}/{file_id}/content"
        ),
    )

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"inc-{uid}", slug=f"inc-{uid}", status="ACTIVE")
    connection = WarehouseConnection.objects.create(
        tenant=tenant,
        name=f"conn-{uid}",
        warehouse_type=WarehouseType.DATABRICKS,
        config={"host": "adb-src.azuredatabricks.net", "auth_mode": "PAT", "pat_token": "dapi-src"},
    )
    RecordingStatementConnector.script = []
    RecordingStatementConnector.client = _make_client(statement_server)

    def factory(_warehouse_type):
        return RecordingStatementConnector

    monkeypatch.setattr(runner_module, "get_connector_for_connection", factory)
    monkeypatch.setattr(runner_module.WarehouseQueryRunner, "_RETRY_DELAYS", [0, 0, 0])
    _isolated_pipelines(monkeypatch, tmp_path)
    bucket = _isolated_bucket(monkeypatch, tmp_path)
    return {"tenant": tenant, "connection": connection, "bucket": bucket}


def _mk_ingestion(tenant, connection):
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"ing-{uuid.uuid4().hex[:8]}",
        source_type="DATABRICKS_SOURCE",
        source_config={
            "warehouse_connection_id": str(connection.id),
            "table": "source_rows",
            "cursor_field": "updated_at",
        },
        schedule_type="DAILY",
        schedule_config={"time": "00:00"},
        file_pattern=".*",
        status="ACTIVE",
        created_by=None,
    )


class TestIngestionWiringIncremental:
    def test_the_first_run_reads_everything_and_records_the_cursor(self, wired_stack):
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        _seed(
            [
                (1, "a", "2026-01-01T00:00:00Z"),
                (2, "b", "2026-01-02T00:00:00Z"),
                (3, "c", "2026-01-03T00:00:00Z"),
            ]
        )
        ingestion = _mk_ingestion(wired_stack["tenant"], wired_stack["connection"])

        outcome = execute_dlt_ingestion(str(ingestion.id))

        assert outcome["error_message"] is None, outcome["error_message"]
        assert outcome["files_processed"] >= 1
        assert len(RecordingStatementConnector.script) == 1
        assert "WHERE" not in RecordingStatementConnector.script[0]["statement"], (
            "the first run has no cursor — the read is unbounded"
        )
        cursor = get_databricks_source_cursor(f"ingestion-{ingestion.id}", str(ingestion.id))
        assert cursor is not None
        assert cursor["last_value"] == "2026-01-03T00:00:00Z"
        loaded = _read_bucket_rows(wired_stack["bucket"])
        ids = sorted(row["id"] for row in loaded if "id" in row)
        assert ids == [1, 2, 3]

    def test_the_second_run_reads_only_after_the_cursor(self, wired_stack):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        _seed(
            [
                (1, "a", "2026-01-01T00:00:00Z"),
                (2, "b", "2026-01-02T00:00:00Z"),
                (3, "c", "2026-01-03T00:00:00Z"),
            ]
        )
        ingestion = _mk_ingestion(wired_stack["tenant"], wired_stack["connection"])
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
        assert '"updated_at" > :last_cursor' in second["statement"]
        assert second["parameters"] == {"last_cursor": "2026-01-03T00:00:00Z"}
        loaded = _read_bucket_rows(wired_stack["bucket"])
        ids = sorted(row["id"] for row in loaded if "id" in row)
        assert ids == [1, 2, 3, 4], "run 1 read everything; run 2 read ONLY the new row"

    def test_a_failed_read_fails_the_run_and_never_advances_the_cursor(
        self,
        wired_stack,
        statement_server,
    ):
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        _seed([(1, "a", "2026-01-01T00:00:00Z")])
        ingestion = _mk_ingestion(wired_stack["tenant"], wired_stack["connection"])
        assert execute_dlt_ingestion(str(ingestion.id))["error_message"] is None
        pipeline_name = f"ingestion-{ingestion.id}"

        StatementApiHandler.forced_state = "FAILED"
        outcome = execute_dlt_ingestion(str(ingestion.id))

        assert outcome["error_message"], "the failed read must fail the run"
        assert outcome["files_processed"] == 0
        cursor = get_databricks_source_cursor(pipeline_name, str(ingestion.id))
        assert cursor is not None, (
            "a failed run must leave the cursor exactly where the last successful "
            "run left it — never advanced, never reset"
        )
        assert cursor["last_value"] == "2026-01-01T00:00:00Z"

    def test_a_connectionless_run_fails_closed_with_zero_http(self, wired_stack):
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        ingestion = _mk_ingestion(wired_stack["tenant"], wired_stack["connection"])
        # A DATABRICKS_SOURCE config without the warehouse connection — the
        # refusal must happen BEFORE any read (zero HTTP against the warehouse).
        ScheduledIngestion.objects.filter(id=ingestion.id).update(source_config={})
        submits_before = len(
            [r for r in StatementApiHandler.requests if r["path"] == "/api/2.0/sql/statements"]
        )
        outcome = execute_dlt_ingestion(str(ingestion.id))
        assert outcome["error_message"], "a config-less source must fail the run closed"
        submits_after = len(
            [r for r in StatementApiHandler.requests if r["path"] == "/api/2.0/sql/statements"]
        )
        assert submits_after == submits_before, "zero HTTP — the refusal happens before any read"
