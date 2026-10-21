"""W3.3 (oss-release-remediation R2-P2) — idempotent re-runs.

Evidence pins (real DB + the REAL dlt 1.30 engine + real filesystem
recording destinations; the only patched symbols are the sanctioned
seams — the pipeline factory, the credential resolver, the discovery
function, and the export-sources reader):

* **Export double-run → no duplicate destination rows** — a re-export of
  the same scope replaces the destination contents (one copy of every
  source row, never two).
* **Ingestion re-run processes only unseen files** — the live path
  filters through the dlt processed-key state: a re-run of the same
  source dispatches NOTHING, and a failed run leaves its keys unmarked
  so the next run retries them.

The destination-row ground truth: dlt 1.30's filesystem destination is
append-only for ``merge`` (falls back with a warning) but applies
``replace`` per run — the probes that pinned this behavior are the
dlt_probe scratch runs recorded in the W3.3 evidence.
"""

from __future__ import annotations

import gzip
import json
import uuid
from pathlib import Path
from unittest import mock

import pytest

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_EXPORT_PIPELINE_FACTORY = "hub.data_movement.export_execution.create_export_pipeline"
_EXPORT_CREDENTIAL_RESOLVER = "hub.data_movement.export_execution.resolve_credentials"
_INGESTION_PIPELINE_FACTORY = "hub.data_movement.ingestion_execution.create_ingestion_pipeline"

_DATABRICKS_DEST = {
    "host": "adb-fixture.cloud.databricks.com",
    "http_path": "/sql/1.0/warehouses/wh-fixture",
    "catalog": "meshant",
    "schema": "staging",
}


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"w33-{uid}",
        slug=f"w33-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"w33-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_contract_source(tenant):
    from hub.apps.assets.models import Asset
    from hub.apps.contracts.models import Contract

    asset = Asset.objects.create(tenant=tenant, name="src", created_by=None)
    Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        status="ACTIVE",
        original_spec_type="ODCS",
        original_spec_version="3.0.2",
        original_format="JSON",
        original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
        validation_status="VALID",
    )
    return asset


def _mk_file(tenant, name):
    from hub.apps.files.models import File

    file_id = uuid.uuid4()
    return File.objects.create(
        tenant=tenant,
        name=name,
        storage_path=f"{tenant.id}/{file_id}/{name}",
        size=0,
    )


def _read_rows(dataset_dir: str, table: str) -> list[dict]:
    table_dir = Path(dataset_dir) / "staging" / table
    rows: list[dict] = []
    for load_file in sorted(table_dir.glob("*.jsonl.gz")):
        with gzip.open(load_file, "rt", encoding="utf-8") as stream:
            for line in stream:
                rows.append(json.loads(line))
    return rows


def _fixture_rows_csv():
    return b"id,name\n1,alpha\n2,beta\n"


class _RecordingPipelineHandle:
    """A REAL dlt pipeline writing to a REAL filesystem destination —
    the recording stand-in for the movement destinations (the 4.4
    recorder convention; the fixture never dials a warehouse)."""

    def __init__(self, pipeline_name: str, dataset_dir: str):
        import dlt

        self.dataset_dir = dataset_dir
        self.pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination=dlt.destinations.filesystem(bucket_url=f"file://{dataset_dir}"),
            dataset_name="staging",
        )
        self.run_calls = 0

    def run(self, resources, credentials=None, **_kwargs):
        self.run_calls += 1
        info = self.pipeline.run(resources)
        return {
            "pipeline_name": "fixture",
            "dataset_name": "staging",
            "loads": [{"load_id": p, "status": "completed"} for p in info.loads_ids],
        }


class TestExportRerunNoDuplicates:
    """A re-export replaces the destination contents — no duplicates."""

    @pytest.fixture
    def fixture_pipeline_factory(self, tmp_path):
        dataset_dir = str(tmp_path / "uc_table_filesystem")
        handles: list[_RecordingPipelineHandle] = []

        def factory(**kwargs):
            handle = _RecordingPipelineHandle(
                pipeline_name=kwargs["pipeline_name"], dataset_dir=dataset_dir
            )
            handles.append(handle)
            return handle

        with mock.patch(_EXPORT_PIPELINE_FACTORY, factory):
            yield {"handles": handles, "dataset_dir": dataset_dir}

    @pytest.fixture
    def fixture_credential_resolver(self):
        def resolver(credential_ref=None):
            assert credential_ref == "fixture-pat"
            return {"token": "dapi-fixture-pat"}

        with mock.patch(_EXPORT_CREDENTIAL_RESOLVER, resolver):
            yield

    @pytest.mark.usefixtures("fixture_credential_resolver")
    def test_double_export_leaves_no_duplicate_destination_rows(self, fixture_pipeline_factory):
        tenant = _mk_tenant()
        user = _mk_user(tenant)
        _mk_contract_source(tenant)
        file_a = _mk_file(tenant, "rows_a.csv")
        file_b = _mk_file(tenant, "rows_b.csv")

        export = ScheduledExport.objects.create(
            tenant=tenant,
            name=f"w33-exp-{uuid.uuid4().hex[:8]}",
            destination_type=DestinationType.DATABRICKS_TABLE,
            destination_config=_DATABRICKS_DEST,
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"file_ids": [str(file_a.id), str(file_b.id)]},
            status=ScheduledExportStatus.ACTIVE,
            credential_ref="fixture-pat",
        )

        from hub.data_movement import export_sources

        payloads = {
            file_a.storage_path: b"id,name\n1,alpha\n2,beta\n",
            file_b.storage_path: b"id,name\n3,gamma\n4,delta\n",
        }

        def fixture_reader(_tenant_id, key):
            return payloads[key]

        service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))
        with mock.patch.object(export_sources, "_default_file_reader", fixture_reader):
            first = service.execute_export(str(export.id), tenant_id=str(tenant.id))
            second = service.execute_export(str(export.id), tenant_id=str(tenant.id))

        assert first.get("error_message") is None
        assert second.get("error_message") is None

        rows = _read_rows(fixture_pipeline_factory["dataset_dir"], "raw_records")
        # Two source files x two rows each, exported TWICE — the
        # destination must hold each source row exactly once. Row order
        # across load files is not a contract (the destination is a set);
        # compare per-file key + row index.
        # The destination adds its own metadata columns (_dlt_load_id/
        # _dlt_id) — the contract is the BUSINESS rows: one copy of each
        # source row, per file key + row index, never duplicated.
        projected = [(r["id"], r["name"], r["_file_key"], r["_row_index"]) for r in rows]
        expected = [
            ("1", "alpha", file_a.storage_path, 0),
            ("2", "beta", file_a.storage_path, 1),
            ("3", "gamma", file_b.storage_path, 0),
            ("4", "delta", file_b.storage_path, 1),
        ]
        projected.sort(key=lambda t: (t[2], t[3]))
        expected.sort(key=lambda t: (t[2], t[3]))
        assert projected == expected, (
            "a re-export must replace the destination, never duplicate rows"
        )


class TestIngestionRerunIncremental:
    """The live ingestion path filters through the dlt processed-key
    state — a re-run of an unchanged source dispatches nothing."""

    @pytest.fixture
    def fixture_ingestion_factory(self, tmp_path):
        dataset_dir = str(tmp_path / "ingest_filesystem")
        handles: list[_RecordingPipelineHandle] = []

        def factory(**kwargs):
            assert set(kwargs) == {"source_type", "pipeline_name", "credential_ref"}
            handle = _RecordingPipelineHandle(
                pipeline_name=kwargs["pipeline_name"], dataset_dir=dataset_dir
            )
            handles.append(handle)
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, factory):
            yield {"handles": handles, "dataset_dir": dataset_dir}

    @pytest.fixture
    def two_file_discovery(self, monkeypatch):
        """The REAL source contract: discovery returns the FULL file list
        on every run — the incremental filter is the execution's job."""
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda obj: [
                {"key": "staging/a.csv", "size": 12},
                {"key": "staging/b.csv", "size": 12},
            ],
        )

    def _ingestion(self, tenant):
        return ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"w33-ing-{uuid.uuid4().hex[:8]}",
            source_type="S3",
            source_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
            schedule_type="DAILY",
            schedule_config={"time": "02:00"},
            file_pattern=".*",
            created_by=None,
        )

    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def test_rerun_dispatches_nothing_and_destination_holds_each_file_once(
        self, fixture_ingestion_factory, two_file_discovery, w38_catalog_seams
    ):
        tenant = _mk_tenant()
        ingestion = self._ingestion(tenant)

        first = self._execute(ingestion.id)
        second = self._execute(ingestion.id)

        assert first.get("error_message") is None
        handle = fixture_ingestion_factory["handles"][0]
        assert handle.run_calls == 1, "the first run dispatches exactly once"
        assert second.get("files_found") == 0, (
            "a re-run of an unchanged source completes with zero work — "
            "the processed-key filter short-circuits before the pipeline"
        )
        assert second.get("error_message") is None

        rows = _read_rows(fixture_ingestion_factory["dataset_dir"], "ingest_files")
        keys = sorted({row.get("file_key") for row in rows})
        assert keys == ["staging/a.csv", "staging/b.csv"], (
            "the destination holds each source file exactly once"
        )

    def test_a_failed_run_leaves_keys_unmarked_for_retry(
        self, fixture_ingestion_factory, two_file_discovery, w38_catalog_seams
    ):
        """The processed keys advance ONLY after a successful load — a
        failed run is retried, and after the retry succeeds the next run
        is a no-op (the SQL-cursor contract on the file path)."""
        tenant = _mk_tenant()
        ingestion = self._ingestion(tenant)

        # The flakiness is keyed on the PIPELINE (shared across the
        # per-execute handles — each execute builds a fresh handle via
        # the factory), so only the first dispatch fails.
        calls = {"count": 0}

        def failing_handle_factory(**kwargs):
            handle = _RecordingPipelineHandle(
                pipeline_name=kwargs["pipeline_name"],
                dataset_dir=fixture_ingestion_factory["dataset_dir"],
            )
            original_run = handle.run

            def flaky_run(resources, credentials=None, **_kw):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise RuntimeError("destination down")
                return original_run(resources, credentials=credentials)

            handle.run = flaky_run
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, failing_handle_factory):
            first = self._execute(ingestion.id)
            second = self._execute(ingestion.id)
            third = self._execute(ingestion.id)

        assert "destination down" in first.get("error_message", "")
        assert calls["count"] == 2, (
            "the failed first run left the keys unmarked, so the second "
            "run retried the same files; after success the third run was "
            "a no-op (no third dispatch)"
        )
        assert second.get("error_message") is None
        assert third.get("files_found") == 0
