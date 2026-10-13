"""TDD pins for the Delta Sharing snapshot job (openspec
add-delta-sharing-server task 5.4) — `JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT`
+ the materialize→stamp→audit spine + the TTL/refresh contract.

The substrate (task 5.3, the sibling session): `DeltaShareSnapshot` rows
(versioned — one row per materialized source version, files manifest,
`expires_at` TTL stamp; NULL treated as EXPIRED by the serving side),
the naming helpers (`share_name_for`/`schema_name_for`/`table_name_for`),
and `latest_snapshot` (the freshness lookup). This suite pins the JOB
that populates those rows.

No mocks: REAL Postgres rows (tenant/asset/connection/Hub Job/audit/
snapshot), the REAL source reader built on the PRODUCTION
``SqlStatementExecutor`` over a REAL threaded local HTTP server (the
statement API's submit answers scripted with real manifests), the REAL
pyarrow parquet writer read back from REAL MinIO S3 through the
production ``S3StorageClient``, the REAL delta-log JSON entry, and the
REAL audit chokepoint. The sanctioned seams are the reader, the
storage client, the audit-DB boundary (the repo's convention), and the
injectable ``now`` — never the unit under test.
"""

import contextlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from django.test import TestCase, override_settings

from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_browse import _setup_tenant

pytestmark = pytest.mark.django_db(transaction=True)

SNAPSHOT_TABLE = "databricks_delta_share_snapshots"
SNAPSHOT_POLICY = "databricks_delta_share_snapshots_tenant_isolation"

# S3 cleanup registry: every test tracks its written keys; the autouse
# fixture best-effort deletes them at teardown (minio accumulates
# otherwise — the per-test table refs are uuid-suffixed, so a test only
# ever deletes its OWN objects).
_TRACKED_BASES: list[str] = []


@pytest.fixture(autouse=True)
def _cleanup_tracked_snapshot_bases():
    yield
    from hub.apps.files.storage import S3StorageClient

    storage = S3StorageClient()
    for base in list(_TRACKED_BASES):
        with contextlib.suppress(Exception):  # cleanup is best-effort hygiene
            storage.delete_prefix(base)
        _TRACKED_BASES.remove(base)


def _mk_connection(tenant, **overrides):
    from hub.apps.warehouses.models import WarehouseConnection, WarehouseType

    kwargs = {
        "tenant": tenant,
        "name": f"conn-{uuid.uuid4().hex[:8]}",
        "warehouse_type": WarehouseType.DATABRICKS,
        "config": {
            "host": "adb-123.azuredatabricks.net",
            "http_path": "/sql/1.0/warehouses/wh-1",
            "pat_token": "dapi-own-token",
        },
    }
    kwargs.update(overrides)
    return WarehouseConnection.objects.create(**kwargs)


def _mk_asset(tenant, connection=None, *, table_ref=None, **overrides):
    from hub.apps.assets.models import Asset, DataStrategy

    kwargs = {
        "tenant": tenant,
        "name": f"asset-{uuid.uuid4().hex[:8]}",
        "data_strategy": DataStrategy.LIVE_QUERY,
        "warehouse_connection": connection,
        "semantic_federate_optout": False,
        "metadata_json": {
            "external_table_ref": table_ref or f"cat.schema.t-{uuid.uuid4().hex[:6]}"
        },
    }
    kwargs.update(overrides)
    return Asset.objects.create(**kwargs)


def _statement_payload(*, state, columns, rows, statement_id):
    return {
        "statement_id": statement_id,
        "status": {"state": state},
        "manifest": {"schema": {"columns": [{"name": col} for col in columns]}},
        "result": {"data_array": rows, "chunk_index": 0, "row_count": len(rows)},
    }


class TestSnapshotJobTypeRegistration:
    def test_job_type_carries_the_delta_share_snapshot_value(self):
        from hub.apps.jobs.models import JobType

        assert JobType.DATABRICKS_DELTA_SHARE_SNAPSHOT == "DATABRICKS_DELTA_SHARE_SNAPSHOT"
        assert "DATABRICKS_DELTA_SHARE_SNAPSHOT" in JobType.values
        assert len("DATABRICKS_DELTA_SHARE_SNAPSHOT") <= 50, "the Job.type column bound"


class TestSnapshotSettings:
    def test_the_three_snapshot_keys_ship_with_the_documented_defaults(self):
        from django.conf import settings

        assert settings.DELTA_SHARE_SNAPSHOT_TTL_SECONDS == 86400
        assert settings.DELTA_SHARE_SNAPSHOT_STORAGE_PREFIX == "delta-share-snapshots"
        assert settings.DELTA_SHARE_SNAPSHOT_MAX_ROWS == 1_000_000


class TestSnapshotJobSpine:
    """The full job spine on the REAL stack (no mocks)."""

    def _setup(self, _monkeypatch, *, ttl_seconds=86400):
        from hub.apps.databricks_admin.tests._fixtures import require_dns

        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection)
        self.now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=UTC)
        self.now_holder = {"value": self.now}
        self.ttl_seconds = ttl_seconds

        from hub.apps.databricks_admin import delta_sharing_snapshot

        self.module = delta_sharing_snapshot

    def _triple(self):
        from hub.apps.databricks_admin.delta_sharing_service import (
            schema_name_for,
            share_name_for,
            table_name_for,
        )

        return (
            share_name_for(self.tenant),
            schema_name_for(self.asset),
            table_name_for(self.asset),
        )

    def _reader(self, port, *, version):
        """A REAL source reader over the PRODUCTION statement executor:
        two real statement-API submissions (the version query, then the
        SELECT) against the local HTTP server — real transport, real
        parsing, no mocks."""

        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.delta_sharing_snapshot import _SourceVersion
        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        def reader(connection, table_ref, tenant_id):
            del connection, table_ref  # the executor owns the transport
            client = DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(tenant_id),
                credential_config={"token": "dapi-snap"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                use_breaker=False,
            )
            executor = SqlStatementExecutor(
                client=client,
                warehouse_id="wh-snap",
                poll_interval_seconds=0.01,
                poll_timeout_seconds=2.0,
            )
            version_result = executor.execute(
                "SELECT COALESCE(MAX(version),0) FROM (DESCRIBE HISTORY cat.schema.t)"
            )
            assert version_result.rows
            assert version_result.rows[0][0] == str(version)
            rows_result = executor.execute("SELECT * FROM cat.schema.t")
            return _SourceVersion(
                version=int(version_result.rows[0][0]),
                columns=rows_result.columns,
                rows=rows_result.rows,
            )

        return reader

    def _scripted_statements(self, *, version, columns, rows):
        RecordingHandler.json_script = [
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED",
                    columns=["version"],
                    rows=[[str(version)]],
                    statement_id="s-ver",
                )
            ),
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED", columns=columns, rows=rows, statement_id="s-data"
                )
            ),
        ]

    def _run(self, reader, **kwargs):
        return self.module.run_snapshot_job(
            asset=self.asset,
            source_reader=reader,
            actor_user=self.admin,
            ttl_seconds=self.ttl_seconds,
            now=lambda: self.now_holder["value"],
            **kwargs,
        )

    def _rows_for_triple(self):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.tenants.request_tenant import tenant_context

        share, schema, table = self._triple()
        with tenant_context(str(self.tenant.id)):
            return list(
                DeltaShareSnapshot.objects.filter(
                    tenant_id=self.tenant.id,
                    share_name=share,
                    schema_name=schema,
                    table_name=table,
                ).order_by("-version")
            )

    def _storage(self):
        from hub.apps.files.storage import S3StorageClient

        return S3StorageClient()

    def _track(self, row):
        share, schema, table = self._triple()
        base = f"delta-share-snapshots/{share}/{schema}/{table}/v{row.version:020d}/"
        _TRACKED_BASES.append(base)
        return base

    def test_the_job_walks_pending_running_completed_and_stamps_the_row(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        columns = ["id", "name"]
        rows = [["1", "alice"], ["2", "bob"]]
        self._scripted_statements(version=7, columns=columns, rows=rows)

        job = self._run(self._reader(local_http_server, version=7))

        # The Hub Job spine: PENDING → RUNNING → COMPLETED persisted.
        from hub.apps.jobs.models import JobStatus

        assert job.type == "DATABRICKS_DELTA_SHARE_SNAPSHOT"
        assert job.status == JobStatus.COMPLETED
        assert job.started_at is not None
        assert job.completed_at is not None
        assert job.resource_type == "ASSET"
        assert str(job.resource_id) == str(self.asset.id)
        assert job.details_json["share_name"] == "meshant"
        assert job.details_json["schema_name"] == self._triple()[1]
        assert job.details_json["table_name"] == self._triple()[2]

        # The stamped row: the version, the files manifest, the TTL.
        rows_stamped = self._rows_for_triple()
        assert len(rows_stamped) == 1
        row = rows_stamped[0]
        assert row.version == 7
        assert row.expires_at == self.now + timedelta(seconds=self.ttl_seconds)
        assert len(row.files) == 1
        assert row.files[0]["partition_values"] == {}
        assert row.files[0]["size"] > 0

        # The terminal result records it.
        assert job.result_json["source_version"] == 7
        assert job.result_json["snapshot_id"] == str(row.id)
        assert job.result_json["reused_existing"] is False

        self._track(row)

    def test_the_written_objects_are_real_parquet_and_a_real_delta_log(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        columns = ["id", "name"]
        rows = [["1", "alice"], ["2", "bob"]]
        self._scripted_statements(version=7, columns=columns, rows=rows)

        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)
        storage = self._storage()

        # The parquet object is a REAL Parquet file with the source rows.
        parquet_key = row.files[0]["path"]
        raw = storage.get_file_content(parquet_key)
        import pyarrow as pa
        import pyarrow.parquet as pq

        table = pq.read_table(pa.py_buffer(raw))
        assert table.column_names == columns
        assert table.to_pydict()["name"] == ["alice", "bob"]
        assert row.files[0]["size"] == len(raw), "the manifest size is the REAL size"

        # The delta-log entry is a REAL Delta protocol JSON entry.
        share, schema, table_name = self._triple()
        log_key = (
            f"delta-share-snapshots/{share}/{schema}/{table_name}/v{7:020d}/"
            f"_delta_log/{7:020d}.json"
        )
        entry = json.loads(storage.get_file_content(log_key))
        assert entry["commitInfo"]["operation"] == "WRITE"
        assert entry["metaData"]["format"]["provider"] == "parquet"
        assert entry["metaData"]["partitionColumns"] == []
        add = entry["add"]
        assert add["path"] == parquet_key, "the add path matches the manifest path"
        assert add["size"] == len(raw)
        assert add["partitionValues"] == {}
        assert add["dataChange"] is True

    def test_re_materializing_the_same_source_version_is_idempotent(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        columns = ["id", "name"]
        self._scripted_statements(version=7, columns=columns, rows=[["1", "alice"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)
        first_expires = row.expires_at

        # The SECOND run reports the SAME source version but DIFFERENT
        # rows — a re-materialization would overwrite the parquet. The
        # idempotent branch must not: same row, same files, fresh stamp.
        self._scripted_statements(version=7, columns=columns, rows=[["1", "mallory"]])
        self.now_holder["value"] += timedelta(seconds=10)
        second = self._run(self._reader(local_http_server, version=7))

        from hub.apps.jobs.models import JobStatus

        assert second.status == JobStatus.COMPLETED
        assert second.result_json["reused_existing"] is True
        rows_after = self._rows_for_triple()
        assert len(rows_after) == 1, "no duplicated versions — the DB grain holds"
        assert rows_after[0].id == row.id
        assert rows_after[0].files == row.files
        assert rows_after[0].expires_at == first_expires + timedelta(seconds=10), (
            "the TTL is re-stamped — freshness renewed, never a new version"
        )
        # The parquet still carries the ORIGINAL rows — never rewritten.
        import pyarrow.parquet as pq

        storage = self._storage()
        raw = storage.get_file_content(row.files[0]["path"])
        import pyarrow as pa

        assert pq.read_table(pa.py_buffer(raw)).to_pydict()["name"] == ["alice"]

    def test_a_new_source_version_writes_a_new_versioned_row(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        columns = ["id", "name"]
        self._scripted_statements(version=7, columns=columns, rows=[["1", "alice"]])
        self._run(self._reader(local_http_server, version=7))
        rows_before = self._rows_for_triple()
        for r in rows_before:
            self._track(r)

        self._scripted_statements(version=8, columns=columns, rows=[["1", "bob"]])
        job = self._run(self._reader(local_http_server, version=8))

        rows_after = self._rows_for_triple()
        assert len(rows_after) == 2, "the version history keeps both rows"
        new_row = next(r for r in rows_after if r.version == 8)
        assert job.result_json["snapshot_id"] == str(new_row.id)
        assert new_row.files[0]["path"] != rows_before[0].files[0]["path"]

        import pyarrow as pa
        import pyarrow.parquet as pq

        raw = self._storage().get_file_content(new_row.files[0]["path"])
        assert pq.read_table(pa.py_buffer(raw)).to_pydict()["name"] == ["bob"]

    def test_the_snapshot_grain_is_unique_at_the_database_level(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)

        # The unique grain is enforced — the model's full_clean raises
        # the ValidationError FIRST (the DB constraint stays the
        # backstop for non-ORM writers): a direct second insert with
        # the same grain fails, never a duplicated version row.
        from django.core.exceptions import ValidationError

        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.tenants.request_tenant import tenant_context

        share, schema, table = self._triple()
        with pytest.raises(ValidationError), tenant_context(str(self.tenant.id)):
            DeltaShareSnapshot.objects.create(
                tenant=self.tenant,
                share_name=share,
                schema_name=schema,
                table_name=table,
                version=7,
                files=row.files,
                expires_at=self.now + timedelta(days=1),
            )

    def test_a_reader_failure_fails_the_job_with_no_row(self, monkeypatch):
        self._setup(monkeypatch)

        def _failing_reader(connection, table_ref, tenant_id):
            del connection, table_ref, tenant_id
            raise RuntimeError("source unavailable")

        job = self._run(_failing_reader)

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "source unavailable" in job.error_message
        assert self._rows_for_triple() == [], "no row is ever stamped for a failed run"

    def test_an_asset_without_a_connection_fails_closed(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        self.asset.warehouse_connection = None
        self.asset.save(update_fields=["warehouse_connection"])

        job = self._run(self._reader(local_http_server, version=1))

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "warehouse connection" in job.error_message
        assert RecordingHandler.requests == [], "ZERO source reads before the refusal"
        assert self._rows_for_triple() == []

    def test_a_duplicate_column_name_is_refused_before_writing(
        self, monkeypatch, local_http_server
    ):
        self._setup(monkeypatch)
        columns = ["id", "id"]
        rows = [["1", "2"]]
        self._scripted_statements(version=7, columns=columns, rows=rows)

        job = self._run(self._reader(local_http_server, version=7))

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "duplicate column" in job.error_message
        assert self._rows_for_triple() == []

    def test_malformed_row_arity_is_refused_before_writing(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        columns = ["id", "name"]
        rows = [["1"]]  # one value for two columns — never a silent truncation
        self._scripted_statements(version=7, columns=columns, rows=rows)

        job = self._run(self._reader(local_http_server, version=7))

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.FAILED
        assert "row" in job.error_message
        assert self._rows_for_triple() == []

    def test_the_audit_trail_records_completed_and_failed(self, monkeypatch, local_http_server):
        from hub.apps.audit.models import AuditEvent

        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)

        completed = AuditEvent.objects.filter(
            tenant=self.tenant, resource_type="DELTA_SHARE_SNAPSHOT"
        ).order_by("timestamp")
        assert len(completed) == 1
        event = completed[0]
        assert event.action == "DATABRICKS_SHARE_SNAPSHOT_COMPLETED"
        assert str(event.resource_id) == str(row.id)
        assert event.actor_user_id == self.admin.id
        assert event.details_json == {
            "share_name": self._triple()[0],
            "schema_name": self._triple()[1],
            "table_name": self._triple()[2],
            "source_version": 7,
            "files_count": 1,
        }, "identifiers only — never credential or storage material"

        # The failure leg: the FAILED action with NO row anchor.
        def _failing_reader(connection, table_ref, tenant_id):
            del connection, table_ref, tenant_id
            raise RuntimeError("source unavailable")

        self._run(_failing_reader)
        failed = AuditEvent.objects.filter(
            tenant=self.tenant,
            resource_type="DELTA_SHARE_SNAPSHOT",
            action="DATABRICKS_SHARE_SNAPSHOT_FAILED",
        ).order_by("-timestamp")
        assert len(failed) == 1
        assert failed[0].resource_id is None
        assert "source unavailable" in failed[0].details_json["error"]

    def test_an_audit_outage_never_blocks_the_snapshot(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])

        def _audit_down(*_args, **_kwargs):
            raise RuntimeError("audit down")

        import hub.apps.audit.utils as audit_utils

        monkeypatch.setattr(audit_utils, "create_audit_event", _audit_down)

        job = self._run(self._reader(local_http_server, version=7))

        from hub.apps.jobs.models import JobStatus

        assert job.status == JobStatus.COMPLETED
        row = self._rows_for_triple()[0]
        self._track(row)
        assert row.version == 7

    @override_settings(DELTA_SHARE_SNAPSHOT_TTL_SECONDS=60)
    def test_the_settings_ttl_drives_the_stamp(self, monkeypatch, local_http_server):
        self._setup(monkeypatch, ttl_seconds=None)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)
        assert row.expires_at == self.now + timedelta(seconds=60)

    def test_the_storage_keys_live_under_the_settings_prefix(self, monkeypatch, local_http_server):
        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._rows_for_triple()[0]
        self._track(row)
        share, schema, table = self._triple()
        expected_base = f"delta-share-snapshots/{share}/{schema}/{table}/v{7:020d}/"
        assert row.files[0]["path"].startswith(expected_base)
        assert row.files[0]["path"].endswith(".snappy.parquet")


class TestSnapshotRefreshContract:
    """The TTL/refresh legs: fresh short-circuits, expired refreshes,
    missing dispatches — the 5.3 data path's calling contract."""

    def _setup(self, _monkeypatch):
        from hub.apps.databricks_admin.tests._fixtures import require_dns

        require_dns()
        self.tenant, self.admin = _setup_tenant()
        self.connection = _mk_connection(self.tenant)
        self.asset = _mk_asset(self.tenant, self.connection)
        self.now = datetime(2026, 9, 12, 12, 0, 0, tzinfo=UTC)
        self.now_holder = {"value": self.now}

        from hub.apps.databricks_admin import delta_sharing_snapshot

        self.module = delta_sharing_snapshot

    def _triple(self):
        from hub.apps.databricks_admin.delta_sharing_service import (
            schema_name_for,
            share_name_for,
            table_name_for,
        )

        return (
            share_name_for(self.tenant),
            schema_name_for(self.asset),
            table_name_for(self.asset),
        )

    def _reader(self, port, *, version):
        from hub.apps.databricks_admin.client import DatabricksApiClient
        from hub.apps.databricks_admin.delta_sharing_snapshot import _SourceVersion
        from hub.apps.databricks_admin.sql_statements import SqlStatementExecutor

        def reader(connection, table_ref, tenant_id):
            del connection, table_ref
            client = DatabricksApiClient(
                base_url=f"http://127.0.0.1:{port}",
                tenant_id=str(tenant_id),
                credential_config={"token": "dapi-snap"},
                timeout_ms=5000,
                max_retries=1,
                retry_base_delay=0.05,
                retry_max_delay=0.1,
                use_breaker=False,
            )
            executor = SqlStatementExecutor(
                client=client,
                warehouse_id="wh-snap",
                poll_interval_seconds=0.01,
                poll_timeout_seconds=2.0,
            )
            executor.execute("SELECT COALESCE(MAX(version),0) FROM (DESCRIBE HISTORY cat.schema.t)")
            rows_result = executor.execute("SELECT * FROM cat.schema.t")
            return _SourceVersion(
                version=version, columns=rows_result.columns, rows=rows_result.rows
            )

        return reader

    def _scripted_statements(self, *, version, columns, rows):
        RecordingHandler.json_script = [
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED",
                    columns=["version"],
                    rows=[[str(version)]],
                    statement_id="s-ver",
                )
            ),
            json.dumps(
                _statement_payload(
                    state="SUCCEEDED", columns=columns, rows=rows, statement_id="s-data"
                )
            ),
        ]

    def _run(self, reader):
        return self.module.run_snapshot_job(
            asset=self.asset,
            source_reader=reader,
            actor_user=self.admin,
            now=lambda: self.now_holder["value"],
        )

    def _snapshot_rows(self):
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.tenants.request_tenant import tenant_context

        share, schema, table = self._triple()
        with tenant_context(str(self.tenant.id)):
            return list(
                DeltaShareSnapshot.objects.filter(
                    tenant_id=self.tenant.id,
                    share_name=share,
                    schema_name=schema,
                    table_name=table,
                ).order_by("-version")
            )

    def _track(self, row):
        share, schema, table = self._triple()
        _TRACKED_BASES.append(
            f"delta-share-snapshots/{share}/{schema}/{table}/v{row.version:020d}/"
        )

    def _ensure(self, reader):
        return self.module.ensure_fresh_snapshot(
            asset=self.asset,
            source_reader=reader,
            actor_user=self.admin,
            now=lambda: self.now_holder["value"],
        )

    def test_a_fresh_snapshot_short_circuits_with_zero_work(self, monkeypatch, local_http_server):
        from hub.apps.jobs.models import Job

        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._snapshot_rows()[0]
        self._track(row)
        jobs_before = Job.objects.filter(tenant=self.tenant).count()
        requests_before = len(RecordingHandler.requests)

        served = self._ensure(self._reader(local_http_server, version=7))

        assert served.id == row.id, "the fresh snapshot is served as-is"
        assert Job.objects.filter(tenant=self.tenant).count() == jobs_before, (
            "a fresh snapshot dispatches NO refresh job"
        )
        assert len(RecordingHandler.requests) == requests_before, (
            "a fresh snapshot performs ZERO source reads"
        )

    def test_an_expired_snapshot_refreshes_and_renews_the_ttl(self, monkeypatch, local_http_server):
        from hub.apps.jobs.models import Job, JobStatus

        self._setup(monkeypatch)
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        self._run(self._reader(local_http_server, version=7))
        row = self._snapshot_rows()[0]
        self._track(row)

        # Expire the stamp (the serving side would treat it as stale).
        row.expires_at = self.now - timedelta(seconds=1)
        row.save(update_fields=["expires_at"])
        jobs_before = Job.objects.filter(tenant=self.tenant).count()

        # The refresh re-reads the SAME source version — the idempotent
        # branch re-stamps the row (freshness renewed, no new version).
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])
        served = self._ensure(self._reader(local_http_server, version=7))

        assert served.id == row.id
        assert served.expires_at > self.now, "the TTL is renewed"
        assert len(self._snapshot_rows()) == 1, "no duplicated versions"
        refresh_jobs = Job.objects.filter(
            tenant=self.tenant, type="DATABRICKS_DELTA_SHARE_SNAPSHOT"
        ).count()
        assert refresh_jobs == jobs_before + 1, "the refresh dispatches exactly ONE job"
        last_job = (
            Job.objects.filter(tenant=self.tenant, type="DATABRICKS_DELTA_SHARE_SNAPSHOT")
            .order_by("-created_at")
            .first()
        )
        assert last_job.status == JobStatus.COMPLETED

    def test_a_missing_snapshot_dispatches_the_job(self, monkeypatch, local_http_server):
        from hub.apps.jobs.models import Job

        self._setup(monkeypatch)
        assert self._snapshot_rows() == []
        columns = ["id"]
        self._scripted_statements(version=7, columns=columns, rows=[["1"]])

        served = self._ensure(self._reader(local_http_server, version=7))

        assert served.version == 7
        assert (
            Job.objects.filter(tenant=self.tenant, type="DATABRICKS_DELTA_SHARE_SNAPSHOT").count()
            == 1
        )
        self._track(served)

    def test_a_failed_refresh_raises_the_classified_error(self, monkeypatch):
        from hub.apps.databricks_admin.delta_sharing_snapshot import DeltaShareSnapshotError

        self._setup(monkeypatch)

        def _failing_reader(connection, table_ref, tenant_id):
            del connection, table_ref, tenant_id
            raise RuntimeError("source unavailable")

        with pytest.raises(DeltaShareSnapshotError) as excinfo:
            self._ensure(_failing_reader)
        assert excinfo.value.code == "DELTA_SHARE_SNAPSHOT_FAILED"
        assert "source unavailable" in str(excinfo.value)
        assert self._snapshot_rows() == []


class TestSnapshotRLS(TestCase):
    """The snapshot table's paired policy FILTERS at runtime (the 1.12
    probe convention) — the CLAUDE.md tenant-isolation contract."""

    def setUp(self):
        from hub.apps.databricks_admin.tests._fixtures import require_dns

        require_dns()
        self.tenant_a, self.admin = _setup_tenant()
        from hub.apps.databricks_admin.models import DeltaShareSnapshot
        from hub.apps.tenants.models import Tenant

        self.tenant_b = Tenant.objects.create(
            name=f"tenant-b-{uuid.uuid4().hex[:8]}",
            slug=f"tenant-b-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
        )
        self.snapshot = DeltaShareSnapshot.objects.create(
            tenant=self.tenant_a,
            share_name="meshant",
            schema_name=f"schema-{uuid.uuid4().hex[:8]}",
            table_name=f"table-{uuid.uuid4().hex[:8]}",
            version=1,
            files=[
                {"id": "f1", "path": "delta-share-snapshots/x", "size": 10, "partition_values": {}}
            ],
            expires_at=datetime(2026, 9, 13, 12, 0, 0),
        )

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def test_the_table_ships_a_paired_policy(self):
        from django.db import connection

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT policyname FROM pg_policies WHERE tablename = %s", [SNAPSHOT_TABLE]
            )
            names = {row[0] for row in cursor.fetchall()}
        assert SNAPSHOT_POLICY in names, "the snapshot table must ship the paired RLS policy"

    def test_foreign_tenants_see_zero_rows(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import _visible_count_as

        probe = self._probe_role()
        assert _visible_count_as(probe, self.tenant_a.id, SNAPSHOT_TABLE) == 1
        assert _visible_count_as(probe, self.tenant_b.id, SNAPSHOT_TABLE) == 0

    def test_no_tenant_context_hides_everything(self):
        from django.db import connection

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                cursor.execute(f"SELECT count(*) FROM {SNAPSHOT_TABLE}")
                assert cursor.fetchone()[0] == 0, (
                    "without a tenant context the snapshot policy must hide everything"
                )
            finally:
                if probe:
                    cursor.execute("RESET ROLE")
