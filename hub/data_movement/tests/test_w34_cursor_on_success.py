"""W3.4 (oss-release-remediation R2-P3) — cursor-on-success.

The ingestion cursor — the dlt processed-key state on the file path and
the per-asset SQL cursor on the DATABRICKS_SOURCE branch — must advance
ONLY when ``files_failed == 0``.

dlt 1.30 ground truth (probed live before the fix, recorded here
because the pre-fix code and the W3.3 fixture both contradicted it):

  * ``pipeline.run()`` returns a ``LoadInfo`` OBJECT — not a Mapping.
    ``result.get("loads", [])`` raises AttributeError, so the pre-fix
    execution took the error path on EVERY real run: zero counts,
    keys never marked, every re-run re-dispatched the full batch.
    The W3.3 recording handle's ``{"loads": [...]}`` dict had hidden
    this — the real engine never returned that shape.
  * The load list lives at ``.load_packages`` (``LoadPackageInfo``
    objects); each package's terminal state is ``.state``
    (``loaded`` / ``failed`` / ``aborted``) — there is no ``.status``.
  * ``.has_failed_jobs`` is the canonical failure signal;
    ``asdict()["load_packages"]`` serializes each package with its
    ``state``.

Pins:

  1. ``load_outcome`` parses the REAL LoadInfo from a REAL
     pipeline.run against a REAL filesystem destination — no mocks.
  2. The live file path, with a pipeline handle that returns the REAL
     LoadInfo object, counts files and marks keys (pre-fix RED: the
     AttributeError path).
  3. A failed-load result leaves the keys unmarked and the next run
     retries the batch (the R2-P3 contract).
  4. A zero-loads result leaves the keys unmarked — fail-closed: an
     empty account must never advance a cursor (pre-fix RED: the
     ``not any(failed)`` form was true for zero loads).
  5. DATABRICKS_SOURCE: a failed load leaves the SQL cursor unchanged
     (pre-fix RED: it advanced unconditionally); a successful load
     advances it to the max row value.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest import mock

import pytest

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

pytestmark = pytest.mark.django_db(transaction=True)

_INGESTION_PIPELINE_FACTORY = "hub.data_movement.ingestion_execution.create_ingestion_pipeline"
_STORAGE_SAVE = "hub.apps.files.storage.S3StorageClient.save_file"
_CONNECTOR_FACTORY = (
    "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_or_fail"
)


def _patch_catalog_env(monkeypatch):
    """The W3.8 catalog-parity environment (the sanctioned seams) — the
    catalog step that runs after a successful load needs the real
    in-memory connector + the S3 storage stand-in + ClamAV off."""
    from .connector_fakes import FakeSourceConnector

    monkeypatch.setattr(
        _STORAGE_SAVE,
        lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: "s3://ok",
    )
    monkeypatch.setattr(
        _CONNECTOR_FACTORY,
        lambda _t: FakeSourceConnector(contents={"staging/a.csv": b"id,name\n1,alpha\n"}),
    )


_RESOLVE_CONNECTION = "hub.data_movement.ingestion_execution._resolve_source_connection"
_RUNNER_FROM_CONNECTION = (
    "hub.data_movement.ingestion_execution.WarehouseQueryRunner.from_connection"
)


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"w34-{uid}",
        slug=f"w34-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_ingestion(tenant, source_type="S3"):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"w34-ing-{uuid.uuid4().hex[:8]}",
        source_type=source_type,
        source_config={
            "bucket": "test-bucket",
            "access_key_id": "AKIATEST",
            "warehouse_connection_id": "wh-conn-fixture",
            "table": "catalog.schema.rows",
            "cursor_field": "updated_at",
        },
        schedule_type="DAILY",
        schedule_config={"time": "02:00"},
        file_pattern=".*",
        created_by=None,
    )


class _RecordingPipelineHandle:
    """A REAL dlt pipeline writing to a REAL filesystem destination —
    the recording stand-in for the movement destinations (the 4.4
    recorder convention; the fixture never dials a warehouse)."""

    def __init__(self, pipeline_name: str, dataset_dir: str):
        import dlt

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


class _RealLoadInfoHandle(_RecordingPipelineHandle):
    """Returns the REAL LoadInfo object — the dlt 1.30 contract the
    execution must parse (the W3.3 fixture hid that it couldn't)."""

    def run(self, resources, credentials=None, **_kwargs):
        self.run_calls += 1
        return self.pipeline.run(resources)


class _DictResultHandle(_RecordingPipelineHandle):
    """Returns a serialized-shape result WITHOUT running the real
    engine — the seam that pins the decision logic for states the real
    engine cannot produce on demand here (failed loads answer with an
    exception on the filesystem destination, which is the OTHER,
    already-covered path)."""

    def __init__(self, pipeline_name: str, dataset_dir: str, loads: list[dict]):
        super().__init__(pipeline_name, dataset_dir)
        self.loads = loads

    def run(self, resources, credentials=None, **_kwargs):
        self.run_calls += 1
        return {"loads": self.loads}


class TestLoadOutcomeParser:
    """``load_outcome`` reads the REAL dlt 1.30 LoadInfo — no mocks."""

    def test_real_loadinfo_reports_loaded_loads(self, tmp_path):
        import dlt

        from hub.data_movement.load_outcome import load_outcome

        pipeline = dlt.pipeline(
            pipeline_name=f"w34-real-{uuid.uuid4().hex[:8]}",
            destination=dlt.destinations.filesystem(bucket_url=f"file://{tmp_path}"),
            dataset_name="staging",
        )

        @dlt.resource
        def rows():
            yield {"id": 1, "name": "alpha"}

        info = pipeline.run([rows()])

        counts = load_outcome(info)
        assert counts["succeeded"] == 1, "a real loaded load must count as succeeded"
        assert counts["failed"] == 0

    def test_none_result_is_empty(self):
        from hub.data_movement.load_outcome import load_outcome

        assert load_outcome(None) == {"succeeded": 0, "failed": 0}

    def test_legacy_fixture_dict_shape_stays_supported(self):
        from hub.data_movement.load_outcome import load_outcome

        counts = load_outcome(
            {
                "loads": [
                    {"load_id": "a", "status": "completed"},
                    {"load_id": "b", "status": "failed"},
                ]
            }
        )
        assert counts == {"succeeded": 1, "failed": 1}

    def test_real_asdict_shape_with_load_packages(self):
        from hub.data_movement.load_outcome import load_outcome

        counts = load_outcome({"load_packages": [{"state": "loaded"}, {"state": "aborted"}]})
        assert counts == {"succeeded": 1, "failed": 1}, (
            "a non-success state (aborted) counts as failed — fail-closed"
        )


class TestFilePathCursorOnSuccess:
    """The live file path advances the processed keys ONLY on a fully
    successful load."""

    @pytest.fixture(autouse=True)
    def _catalog_env(self, monkeypatch, settings):
        settings.CLAMAV_ENABLED = False
        _patch_catalog_env(monkeypatch)

    @pytest.fixture
    def dataset_dir(self, tmp_path):
        return str(tmp_path / "w34_filesystem")

    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def _patch_discovery(self, monkeypatch):
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda obj: [
                {"key": "staging/a.csv", "size": 12},
                {"key": "staging/b.csv", "size": 12},
            ],
        )

    def test_real_loadinfo_execution_counts_and_marks(
        self, monkeypatch, dataset_dir, w38_catalog_seams
    ):
        """The execution must parse the REAL LoadInfo — pre-fix it took
        the AttributeError path on every real run (zero counts, keys
        never marked, the audit recorded a FAILED run)."""
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)

        handles = []

        def factory(**kwargs):
            handle = _RealLoadInfoHandle(kwargs["pipeline_name"], dataset_dir)
            handles.append(handle)
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, factory):
            first = self._execute(ingestion.id)
            second = self._execute(ingestion.id)

        assert first.get("error_message") is None, first.get("error_message")
        assert first["files_processed"] >= 1, (
            "a real loaded load must count as processed, not crash the parse"
        )
        assert first["files_failed"] == 0
        assert second.get("error_message") is None
        assert second["files_found"] == 0, (
            "the successful run marked the keys — the re-run short-circuits"
        )

    def test_failed_load_leaves_keys_unmarked_for_retry(
        self, monkeypatch, dataset_dir, w38_catalog_seams
    ):
        """R2-P3: a result whose load FAILED (without raising) must not
        advance the cursor — the next run retries the batch."""
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)

        calls = {"count": 0}

        def flaky_factory(**kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                return _DictResultHandle(
                    kwargs["pipeline_name"], dataset_dir, [{"load_id": "a", "status": "failed"}]
                )
            return _RealLoadInfoHandle(kwargs["pipeline_name"], dataset_dir)

        with mock.patch(_INGESTION_PIPELINE_FACTORY, flaky_factory):
            first = self._execute(ingestion.id)
            second = self._execute(ingestion.id)
            third = self._execute(ingestion.id)

        assert first["files_failed"] >= 1
        assert first["files_processed"] == 0
        assert first.get("error_message") is None
        assert second.get("error_message") is None
        assert second["files_processed"] >= 1, (
            "the failed run left the keys unmarked — the next run retried"
        )
        assert third["files_found"] == 0, "after the successful retry, a further run is a no-op"

    def test_zero_loads_never_advance_the_cursor(self, monkeypatch, dataset_dir, w38_catalog_seams):
        """Fail-closed: a result accounting for ZERO loads must not mark
        the pending keys (pre-fix the ``not any(failed)`` form was true
        for zero loads and marked them)."""
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)

        def empty_factory(**kwargs):
            return _DictResultHandle(kwargs["pipeline_name"], dataset_dir, [])

        with mock.patch(_INGESTION_PIPELINE_FACTORY, empty_factory):
            first = self._execute(ingestion.id)

        with mock.patch(
            _INGESTION_PIPELINE_FACTORY,
            lambda **kw: _RealLoadInfoHandle(kw["pipeline_name"], dataset_dir),
        ):
            second = self._execute(ingestion.id)

        assert first["files_found"] == 0
        assert second["files_processed"] >= 1, (
            "the zero-load run must not have marked anything — the next run "
            "still dispatches the pending batch"
        )


class TestDatabricksSourceCursorOnSuccess:
    """The DATABRICKS_SOURCE branch advances the SQL cursor ONLY on a
    fully successful load (pre-fix: unconditional)."""

    @pytest.fixture(autouse=True)
    def _catalog_env(self, monkeypatch, settings):
        settings.CLAMAV_ENABLED = False
        monkeypatch.setattr(
            _STORAGE_SAVE,
            lambda self, tenant_id, file_id, file_content: "s3://ok",
        )

    @pytest.fixture
    def fixture_databricks(self, tmp_path, monkeypatch):
        from hub.data_movement import ingestion_execution

        dataset_dir = str(tmp_path / "w34_databricks")
        handles = []

        def factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], dataset_dir)
            handles.append(handle)
            return handle

        monkeypatch.setattr(
            ingestion_execution,
            "_resolve_source_connection",
            lambda obj, config: SimpleNamespace(id="wh-conn-fixture"),
        )

        class _FakeRunner:
            def __init__(self, rows):
                self._rows = rows
                self.sql = None
                self.params = None

            def execute(self, sql, params):
                self.sql = sql
                self.params = params
                return self._rows

        runner = _FakeRunner(
            [{"id": 1, "updated_at": "2026-01-01"}, {"id": 2, "updated_at": "2026-01-02"}]
        )
        monkeypatch.setattr(
            ingestion_execution.WarehouseQueryRunner,
            "from_connection",
            classmethod(lambda cls, connection, query_type: runner),
        )
        return {"factory": factory, "handles": handles, "runner": runner}

    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def _cursor(self, ingestion):
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor

        pipeline_name = f"ingestion-{ingestion.id}"
        asset_key = str(ingestion.id)
        return get_databricks_source_cursor(pipeline_name, asset_key)

    def test_failed_load_leaves_databricks_cursor_unchanged(self, fixture_databricks):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, source_type="DATABRICKS_SOURCE")

        # The handle must exist under the SAME pipeline name the
        # execution derives (the dlt state — and therefore the cursor —
        # is keyed by pipeline name); its run returns a failed-load
        # result WITHOUT raising (the R2-P3 scenario).
        def failing_factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], "/tmp/w34-db-failed")

            def failed_run(resources, credentials=None, **_kw):
                handle.run_calls += 1
                return {"loads": [{"load_id": "a", "status": "failed"}]}

            handle.run = failed_run
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, failing_factory):
            outcome = self._execute(ingestion.id)

        assert outcome["files_failed"] >= 1
        assert self._cursor(ingestion) is None, (
            "a failed load must leave the SQL cursor unchanged (pre-fix: advanced unconditionally)"
        )

    def test_successful_load_advances_databricks_cursor(
        self, fixture_databricks, w38_catalog_seams
    ):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, source_type="DATABRICKS_SOURCE")

        with mock.patch(_INGESTION_PIPELINE_FACTORY, fixture_databricks["factory"]):
            outcome = self._execute(ingestion.id)

        assert outcome.get("error_message") is None, outcome.get("error_message")
        assert outcome["files_failed"] == 0
        cursor = self._cursor(ingestion)
        assert cursor is not None
        assert cursor["last_value"] == "2026-01-02", (
            "the cursor advances to the max row value only on success"
        )
