"""W3.8 (oss-release-remediation R2-P7/D6) — dlt ingestion catalog parity.

The D6 decision: parity-first — the dlt path creates REAL File/Dataset
records before pilot E2E sign-off, never a fabricated count.  The pre-fix
spine set ``datasets_created = files_processed`` (a load-package count
echo) while the catalog stayed empty — datasets invisible to the catalog
(the D6 functional gap on pilot journey 3.4).

Evidence pins (real DB + the REAL dlt 1.30 engine + real filesystem
recording destinations + a real in-memory source connector; the only
patched symbols are the sanctioned seams — the pipeline factory, the
discovery function, the source-connector factory, and the S3 storage
boundary):

* **A successful file run creates one File + one Dataset per ingested
  file** — ``datasets_created`` counts the REAL rows.
* **The run row counts real rows** — ``run.datasets_created ==`` the
  number of Dataset rows the run's files actually have (the task's
  evidence pin), and a replay returns the recorded count.
* **A re-run never duplicates catalog rows** — the processed-key filter
  short-circuits before the pipeline.
* **A catalog failure fails the run honestly and the retry recovers
  without duplicates** — the per-file creation is idempotent by source
  key, so the crash window between row commit and key marking is safe.
* **DATABRICKS_SOURCE materializes its rows** — one File + Dataset per
  successful read, versioned per run; the SQL cursor advances only when
  the catalog row landed.
"""

from __future__ import annotations

import uuid
from unittest import mock

import pytest

from hub.apps.scheduled_ingestion.models import ScheduledIngestion
from hub.apps.scheduled_ingestion.services import IngestionService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

from .connector_fakes import FakeSourceConnector

pytestmark = pytest.mark.django_db(transaction=True)

_INGESTION_PIPELINE_FACTORY = "hub.data_movement.ingestion_execution.create_ingestion_pipeline"
_STORAGE_SAVE = "hub.apps.files.storage.S3StorageClient.save_file"
_CONNECTOR_FACTORY = (
    "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_or_fail"
)

_CSV_ROWS = b"id,name\n1,alpha\n2,beta\n"


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"w38-{uid}",
        slug=f"w38-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_user(tenant):
    return User.objects.create_user(
        email=f"w38-{uuid.uuid4().hex[:8]}@meshant.test",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )


def _mk_ingestion(tenant, *, source_type="S3", auto_create_asset=False, auto_activate=False):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"w38-ing-{uuid.uuid4().hex[:8]}",
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
        auto_create_asset=auto_create_asset,
        auto_activate=auto_activate,
        created_by=None,
    )


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


def _patch_storage(monkeypatch, *, side_effect=None):
    """The sanctioned S3 storage-boundary stand-in (the repo's documented
    only-mock pattern for suites that don't run an S3 endpoint).
    Keyword-tolerant: the core calls save_file(tenant_id=...,
    file_id=..., file_content=...) — all keyword arguments."""
    if side_effect is not None:
        monkeypatch.setattr(_STORAGE_SAVE, mock.Mock(side_effect=side_effect))
    else:
        monkeypatch.setattr(
            _STORAGE_SAVE,
            lambda *args, tenant_id=None, file_id=None, file_content=None, **kwargs: (
                f"{tenant_id}/{file_id}/content"
            ),
        )


@pytest.fixture
def catalog_env(monkeypatch, tmp_path):
    """The W3.8 catalog environment: a real dlt filesystem pipeline, a
    real in-memory source connector serving CSV content, the S3 storage
    boundary stand-in, and ClamAV disabled (the SCAN_UNAVAILABLE branch —
    no scan enqueue dependency)."""
    dataset_dir = str(tmp_path / "w38_filesystem")
    handles: list[_RecordingPipelineHandle] = []

    def factory(**kwargs):
        assert set(kwargs) == {"source_type", "pipeline_name", "credential_ref"}
        handle = _RecordingPipelineHandle(
            pipeline_name=kwargs["pipeline_name"], dataset_dir=dataset_dir
        )
        handles.append(handle)
        return handle

    monkeypatch.setattr(_INGESTION_PIPELINE_FACTORY, factory)
    connector = FakeSourceConnector(
        contents={"staging/a.csv": _CSV_ROWS, "staging/b.csv": _CSV_ROWS}
    )
    monkeypatch.setattr(_CONNECTOR_FACTORY, lambda _t: connector)
    _patch_storage(monkeypatch)
    return {"handles": handles, "dataset_dir": dataset_dir, "connector": connector}


class TestFilePathCatalogParity:
    @pytest.fixture(autouse=True)
    def _clamav_disabled(self, settings):
        settings.CLAMAV_ENABLED = False

    def _patch_discovery(self, monkeypatch, files):
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(ingestion_execution, "_discover_source_files", lambda obj: files)

    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def _two_file_discovery(self, monkeypatch):
        self._patch_discovery(
            monkeypatch,
            [
                {"key": "staging/a.csv", "size": len(_CSV_ROWS)},
                {"key": "staging/b.csv", "size": len(_CSV_ROWS)},
            ],
        )

    def test_a_successful_run_creates_one_file_and_dataset_per_ingested_file(
        self, catalog_env, monkeypatch
    ):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File, FileStatus

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, auto_create_asset=True)
        self._two_file_discovery(monkeypatch)

        outcome = self._execute(ingestion.id)

        assert outcome.get("error_message") is None, outcome.get("error_message")
        assert outcome["datasets_created"] == 2, (
            "datasets_created must count the REAL File/Dataset pairs, "
            "never the fabricated files_processed echo"
        )
        files = list(File.objects.filter(tenant=tenant).order_by("name"))
        assert [f.name for f in files] == ["a.csv", "b.csv"]
        for file_row in files:
            assert file_row.status == FileStatus.ACTIVE
            assert file_row.storage_path, "the file content landed in hub storage"
            assert file_row.content_sha256
            markers = file_row.metadata_json
            assert markers.get("scheduled_ingestion_id") == str(ingestion.id)
            assert markers.get("source_key") in {"staging/a.csv", "staging/b.csv"}

        datasets = list(Dataset.objects.filter(tenant=tenant).order_by("file__name"))
        assert len(datasets) == 2
        ingestion.refresh_from_db()
        for dataset in datasets:
            assert dataset.file in files
            assert dataset.format == "CSV"
            assert dataset.asset_id == ingestion.asset_id, (
                "the dataset links to the ingestion's asset"
            )
        assert ingestion.asset_id is not None, "auto_create_asset created the asset"

    def test_the_run_row_counts_real_dataset_rows(self, catalog_env, monkeypatch):
        from hub.apps.datasets.models import Dataset

        tenant = _mk_tenant()
        user = _mk_user(tenant)
        ingestion = _mk_ingestion(tenant, auto_create_asset=True)
        self._two_file_discovery(monkeypatch)

        service = IngestionService(tenant_id=str(tenant.id), user_id=str(user.id))
        key = "w38-replay-key"
        result = service.execute_ingestion_run(
            str(ingestion.id),
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            idempotency_key=key,
        )

        assert result["run_status"] == "COMPLETED"
        real_rows = Dataset.objects.filter(tenant=tenant).count()
        assert real_rows == 2
        assert result["datasets_created"] == real_rows, (
            "the run row's datasets_created equals the REAL Dataset rows "
            "created for the run — the W3.8 evidence pin"
        )
        # The replay returns the RECORDED count (pre-fix: hardcoded 0).
        replay = service.execute_ingestion_run(
            str(ingestion.id),
            tenant_id=str(tenant.id),
            user_id=str(user.id),
            idempotency_key=key,
        )
        assert replay["replayed"] is True
        assert replay["datasets_created"] == real_rows

    def test_a_rerun_never_duplicates_catalog_rows(self, catalog_env, monkeypatch):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._two_file_discovery(monkeypatch)

        first = self._execute(ingestion.id)
        second = self._execute(ingestion.id)

        assert first.get("error_message") is None
        assert first["datasets_created"] == 2
        assert second["files_found"] == 0, "the processed-key filter short-circuits the re-run"
        assert File.objects.filter(tenant=tenant).count() == 2
        assert Dataset.objects.filter(tenant=tenant).count() == 2

    def test_a_catalog_failure_fails_the_run_and_the_retry_recovers_without_duplicates(
        self, catalog_env, monkeypatch
    ):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._two_file_discovery(monkeypatch)

        # The storage boundary fails for the WHOLE first attempt — the
        # catalog phase must surface the failure honestly (files_failed +
        # error_message) and leave the processed keys unmarked.
        calls = {"n": 0}

        def flaky_save(*args, tenant_id=None, file_id=None, file_content=None, **kwargs):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise OSError("storage down")
            return f"{tenant_id}/{file_id}/content"

        _patch_storage(monkeypatch, side_effect=flaky_save)

        first = self._execute(ingestion.id)
        assert first["files_failed"] >= 1, "the catalog failure counts as a failed file"
        assert "storage down" in (first.get("error_message") or "")
        assert File.objects.filter(tenant=tenant).count() == 0, (
            "the failed creation rolled back — no orphan rows"
        )

        second = self._execute(ingestion.id)
        assert second.get("error_message") is None
        assert second["datasets_created"] == 2, "the retry creates the missing rows"
        assert File.objects.filter(tenant=tenant).count() == 2
        assert Dataset.objects.filter(tenant=tenant).count() == 2

        third = self._execute(ingestion.id)
        assert third["files_found"] == 0, "after the recovered run, a further run is a no-op"

    def test_an_unsupported_file_counts_failed_and_never_duplicates(self, catalog_env, monkeypatch):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(
            monkeypatch,
            [
                {"key": "staging/a.csv", "size": len(_CSV_ROWS)},
                {"key": "staging/b.exe", "size": 12},
            ],
        )

        first = self._execute(ingestion.id)

        assert first["files_failed"] == 1
        assert "b.exe" in (first.get("error_message") or "")
        assert first["datasets_created"] == 1, "the supported file's pair was created"
        assert File.objects.filter(tenant=tenant).count() == 1
        assert Dataset.objects.filter(tenant=tenant).count() == 1

        # The retry re-attempts the whole batch: the created pair is
        # RECOVERED (never duplicated), the unsupported file fails again.
        second = self._execute(ingestion.id)
        assert second["files_failed"] == 1
        assert second["datasets_created"] == 1
        assert File.objects.filter(tenant=tenant).count() == 1, "no duplicates after retry"
        assert Dataset.objects.filter(tenant=tenant).count() == 1


class _DatabricksFixture:
    """The DATABRICKS_SOURCE seams (the W3.4 convention): a real
    filesystem pipeline, a scripted connection/runner, the S3 storage
    boundary stand-in, and ClamAV disabled."""

    def __init__(self, monkeypatch, tmp_path, rows):
        from types import SimpleNamespace

        from hub.data_movement import ingestion_execution

        dataset_dir = str(tmp_path / "w38_databricks")
        self.handles: list[_RecordingPipelineHandle] = []

        def factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], dataset_dir)
            self.handles.append(handle)
            return handle

        monkeypatch.setattr(_INGESTION_PIPELINE_FACTORY, factory)
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

        self.runner = _FakeRunner(rows)
        monkeypatch.setattr(
            ingestion_execution.WarehouseQueryRunner,
            "from_connection",
            classmethod(lambda cls, connection, query_type: self.runner),
        )
        _patch_storage(monkeypatch)

    def set_rows(self, rows):
        self.runner._rows = rows


class TestDatabricksSourceCatalogParity:
    @pytest.fixture(autouse=True)
    def _clamav_disabled(self, settings):
        settings.CLAMAV_ENABLED = False

    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def _cursor(self, ingestion):
        from hub.data_movement.dlt_incremental import get_databricks_source_cursor

        pipeline_name = f"ingestion-{ingestion.id}"
        return get_databricks_source_cursor(pipeline_name, str(ingestion.id))

    def test_a_successful_read_materializes_file_and_dataset_rows(self, monkeypatch, tmp_path):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        rows = [
            {"id": 1, "updated_at": "2026-01-01"},
            {"id": 2, "updated_at": "2026-01-02"},
        ]
        _DatabricksFixture(monkeypatch, tmp_path, rows)
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, source_type="DATABRICKS_SOURCE")

        outcome = self._execute(ingestion.id)

        assert outcome.get("error_message") is None, outcome.get("error_message")
        assert outcome["datasets_created"] == 1, "the read materializes ONE real File+Dataset"
        files = list(File.objects.filter(tenant=tenant))
        assert len(files) == 1
        assert files[0].name.endswith(".json")
        datasets = list(Dataset.objects.filter(tenant=tenant))
        assert len(datasets) == 1
        assert datasets[0].file_id == files[0].id
        assert datasets[0].format == "JSON"
        assert datasets[0].row_count == 2, "the dataset row count is the REAL row count"
        cursor = self._cursor(ingestion)
        assert cursor is not None
        assert cursor["last_value"] == "2026-01-02"

    def test_a_second_run_versions_the_dataset(self, monkeypatch, tmp_path):
        from hub.apps.datasets.models import Dataset

        fixture = _DatabricksFixture(
            monkeypatch,
            tmp_path,
            [{"id": 1, "updated_at": "2026-01-01"}],
        )
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, source_type="DATABRICKS_SOURCE", auto_create_asset=True)

        first = self._execute(ingestion.id)
        assert first.get("error_message") is None, first.get("error_message")

        fixture.set_rows(
            [
                {"id": 1, "updated_at": "2026-01-01"},
                {"id": 2, "updated_at": "2026-01-02"},
            ]
        )
        second = self._execute(ingestion.id)
        assert second.get("error_message") is None, second.get("error_message")

        datasets = list(Dataset.objects.filter(tenant=tenant).order_by("version"))
        assert [d.version for d in datasets] == [1, 2], "each successful read is a new version"
        assert datasets[1].parent_version_id == datasets[0].id

    def test_a_catalog_failure_never_advances_the_cursor(self, monkeypatch, tmp_path):
        from hub.apps.datasets.models import Dataset

        _DatabricksFixture(
            monkeypatch,
            tmp_path,
            [{"id": 1, "updated_at": "2026-01-01"}],
        )

        def failing_save(*args, tenant_id=None, file_id=None, file_content=None, **kwargs):
            raise OSError("storage down")

        _patch_storage(monkeypatch, side_effect=failing_save)

        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant, source_type="DATABRICKS_SOURCE")

        outcome = self._execute(ingestion.id)

        assert outcome["files_failed"] >= 1, "the catalog failure counts as a failed load"
        assert "storage down" in (outcome.get("error_message") or "")
        assert self._cursor(ingestion) is None, (
            "the SQL cursor advances ONLY when the catalog row landed — "
            "a failed materialization is retried from the same bound"
        )
        assert Dataset.objects.filter(tenant=tenant).count() == 0
