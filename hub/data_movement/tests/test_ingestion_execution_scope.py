"""TDD pins for the ingestion entrypoint wiring (openspec
wire-databricks-dlt-movement task 6.5): the pipeline.run executes INSIDE
the guard-bypass scope via ``MovementPipelineExecutor`` — and the guard
is restored the moment the run returns.

Real everything except the sanctioned module-symbol seam: the
``create_ingestion_pipeline`` symbol on the ``ingestion_execution``
module is replaced with a recording REAL pipeline (the 4.4/5.3
convention) whose run() asserts the guard contract from INSIDE the run.
"""

import uuid

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def tenant():
    from tests.factories import TenantFactory

    return TenantFactory.create_tenant()


class _RecordingPipeline:
    """A REAL minimal pipeline standing in for the dlt pipeline at the
    sanctioned factory symbol."""

    def __init__(self):
        self.run_calls = 0
        self.run_kwargs: list[dict] = []

    def run(self, *args, **kwargs):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        self.run_calls += 1
        self.run_kwargs.append((args, kwargs))
        ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")
        return {"loads": [{"load_id": "l1", "status": "completed"}]}


@pytest.fixture
def recording_pipeline(monkeypatch):
    from hub.data_movement import ingestion_execution

    recorder = _RecordingPipeline()

    def factory(**kwargs):
        # The pin: the entrypoint hands the production kwargs through.
        assert set(kwargs) == {"source_type", "pipeline_name", "credential_ref"}
        return recorder

    monkeypatch.setattr(ingestion_execution, "create_ingestion_pipeline", factory)
    return recorder


@pytest.fixture
def one_file_discovery(monkeypatch):
    """Discovery seam: the connector factory lives in the prefect-
    integration service package — replace the module symbol with a
    one-file source so the pipeline run still executes WITHOUT the
    real connector (tests that need the REAL discovery path do not
    use this fixture)."""
    from hub.data_movement import ingestion_execution

    monkeypatch.setattr(
        ingestion_execution,
        "_discover_source_files",
        lambda obj: [{"key": "staging/file-1.csv", "size": 12}],
    )


def _ingestion(tenant):
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"ing-scope-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
        schedule_type="DAILY",
        schedule_config={"time": "02:00"},
        file_pattern=".*",
        created_by=None,
    )


def _execute(ingestion_id):
    from hub.data_movement.ingestion_execution import execute_dlt_ingestion

    return execute_dlt_ingestion(ingestion_id)


class TestIngestionRunsInsideTheGuardScope:
    def test_the_pipeline_run_executes_inside_the_scope(
        self, tenant, recording_pipeline, one_file_discovery, w38_catalog_seams
    ):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        ingestion = _ingestion(tenant)

        result = _execute(ingestion.id)

        assert result["error_message"] is None
        assert recording_pipeline.run_calls == 1

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

    def test_a_failed_run_still_restores_the_guard(
        self, tenant, recording_pipeline, one_file_discovery
    ):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        ingestion = _ingestion(tenant)

        def boom(*args, **kwargs):
            raise RuntimeError(f"destination down ({len(args)} positional, {len(kwargs)} kw)")

        recording_pipeline.run = boom

        result = _execute(ingestion.id)

        assert "destination down" in result["error_message"]

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

    def test_empty_source_completes_without_a_pipeline_run(
        self, tenant, recording_pipeline, monkeypatch
    ):
        """An empty source is the legacy terminal contract: COMPLETED with
        zero counts and NO dlt run (dlt 1.30 rejects an empty resource
        list with ResourceNameMissing — the run must skip the pipeline
        entirely)."""
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(ingestion_execution, "_discover_source_files", lambda obj: [])

        result = _execute(_ingestion(tenant).id)

        assert result["error_message"] is None
        assert result["files_found"] == 0
        assert result["files_processed"] == 0
        assert recording_pipeline.run_calls == 0

    def test_the_pipeline_receives_the_discovered_files_resource(
        self, tenant, recording_pipeline, one_file_discovery, w38_catalog_seams
    ):
        """Non-empty discovery hands the pipeline an ``ingest_files``
        resource built from the discovered file list."""
        result = _execute(_ingestion(tenant).id)

        assert result["error_message"] is None
        assert recording_pipeline.run_calls == 1
        kwargs = recording_pipeline.run_kwargs[0][1]
        resources = kwargs.get("resources") or recording_pipeline.run_kwargs[0][0][0]
        assert len(resources) == 1
        assert getattr(resources[0], "name", None) == "ingest_files"

    def test_credential_less_s3_source_fails_instead_of_silently_completing(
        self, tenant, recording_pipeline, monkeypatch
    ):
        """A credential-less object-store config is NOT silently treated
        as empty anymore (the placeholder guard was retired with the real
        S3 create form, 2026-10-03): the connector is actually consulted
        and its failure propagates to the run's error_message — a
        misconfigured source must FAIL honestly, never COMPLETE with
        zero files (false-success defect class)."""
        from hub.apps.orchestration.workflows import scheduled_ingestion as wf
        from hub.apps.scheduled_ingestion.models import ScheduledIngestion

        calls: list[dict] = []

        class _FailingConnector:
            def discover_files(self, config, pattern):
                calls.append(config)
                raise ConnectionError("S3 endpoint refused (no credentials)")

        monkeypatch.setattr(wf, "_get_source_connector_or_fail", lambda _t: _FailingConnector())

        placeholder = ScheduledIngestion.objects.create(
            tenant=tenant,
            name=f"ing-placeholder-{uuid.uuid4().hex[:8]}",
            source_type="S3",
            source_config={"bucket": "placeholder-bucket"},
            schedule_type="DAILY",
            schedule_config={"time": "02:00"},
            file_pattern=".*",
            created_by=None,
        )

        result = _execute(placeholder.id)

        assert "S3 endpoint refused" in (result["error_message"] or "")
        assert result["files_found"] == 0
        assert len(calls) == 1  # the connector was consulted, not short-circuited
        assert calls[0] == {"bucket": "placeholder-bucket"}
        assert recording_pipeline.run_calls == 0


class TestDiscoveryNormalization:
    """The connectors return list[str] object keys (the legacy workflow's
    contract — services/prefect-integration/connectors/s3_connector.py
    discover_files), while the dlt ``ingest_files`` resource consumes
    ``{"key": ...}`` dicts. The boundary normalization in
    ``_discover_source_files`` must bridge the two — without it a REAL
    S3 source with files fails every run with
    ``AttributeError: 'str' object has no attribute 'get'``
    (JOURNEY-INGESTION-001 real-work blocker, 2026-10-03)."""

    def test_discovered_string_keys_are_normalized_to_dicts(
        self, tenant, monkeypatch
    ):
        from hub.apps.orchestration.workflows import scheduled_ingestion as wf
        from hub.data_movement import ingestion_execution

        class _StringConnector:
            def discover_files(self, config, pattern):
                assert config.get("access_key_id") == "AKIATEST"
                return ["staging/a.csv", "staging/b.csv"]

        monkeypatch.setattr(wf, "_get_source_connector_or_fail", lambda _t: _StringConnector())

        ingestion = _ingestion(tenant)
        files = ingestion_execution._discover_source_files(ingestion)

        assert files == [{"key": "staging/a.csv"}, {"key": "staging/b.csv"}]

    def test_string_discovery_runs_ingest_files_without_attribute_error(
        self, tenant, recording_pipeline, monkeypatch, w38_catalog_seams
    ):
        """THE regression pin: bare-string discovery (the REAL S3Connector
        shape) must flow through ``ingest_files`` without the
        AttributeError that failed every real run."""
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda obj: ["staging/file-1.csv"],
        )

        result = _execute(_ingestion(tenant).id)

        assert result["error_message"] is None
        assert recording_pipeline.run_calls == 1
        kwargs = recording_pipeline.run_kwargs[0][1]
        resources = kwargs.get("resources") or recording_pipeline.run_kwargs[0][0][0]
        rows = list(resources[0])
        assert rows[0]["file_key"] == "staging/file-1.csv"

    def test_dict_discovery_passes_through_unchanged(self, tenant, monkeypatch):
        from hub.apps.orchestration.workflows import scheduled_ingestion as wf
        from hub.data_movement import ingestion_execution

        class _DictConnector:
            def discover_files(self, config, pattern):
                return [{"key": "x.csv", "size": 12}]

        monkeypatch.setattr(wf, "_get_source_connector_or_fail", lambda _t: _DictConnector())

        files = ingestion_execution._discover_source_files(_ingestion(tenant))

        assert files == [{"key": "x.csv", "size": 12}]
