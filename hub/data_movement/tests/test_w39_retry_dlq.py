"""W3.9 (oss-release-remediation F5/F6/F17) — bounded retry for
retryable failures + the DLQ retry effect.

The evidence contract:

  * **transient-failure-retried** — a RETRYABLE failure (connection /
    timeout / refused) inside the dlt execution is retried with backoff
    and the run succeeds; the retry count is recorded.
  * **bounded** — a persistently retryable failure stops after the
    bound (no infinite loop) and surfaces the error honestly.
  * **permanent failures are NOT retried** — a schema/permission-class
    failure fails immediately (exactly one attempt).
  * **DLQ retry effect** — retrying a DLQ item actually re-queues the
    file for the LIVE (dlt processed-key) state: the next execution
    re-dispatches it.

The pre-fix state this drives out: the dead ``dlt_retry`` module (its
``retry_failed`` references the removed ``LoadInfo.loads`` and the
removed ``last_trace.last_trace`` chain — it AttributeErrors on dlt
1.30), no retry anywhere on the dlt path (a transient failure
terminal-FAILED the run forever), and ``DeadLetterQueueManager.
retry_file`` had no effect on the dlt state (it only cleared the
legacy per-file failed state).

No mocks: the real engine, the real dlt pipelines, the real DLQ model —
the only patched symbols are the sanctioned seams (the pipeline factory
and the discovery function).
"""

from __future__ import annotations

import uuid
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


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"w39-{uid}",
        slug=f"w39-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _patch_catalog_env(monkeypatch):
    """The W3.8 catalog-parity environment (the sanctioned seams): a real
    in-memory source connector serving the discovered files, the S3
    storage boundary stand-in, and ClamAV disabled — the catalog step
    that runs after a successful load needs all three."""
    from .connector_fakes import FakeSourceConnector

    monkeypatch.setattr(_STORAGE_SAVE, lambda self, tenant_id, file_id, file_content: "s3://ok")
    monkeypatch.setattr(
        _CONNECTOR_FACTORY,
        lambda _t: FakeSourceConnector(contents={"staging/a.csv": b"id,name\n1,alpha\n"}),
    )


def _mk_ingestion(tenant):
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"w39-ing-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={
            "bucket": "test-bucket",
            "access_key_id": "AKIATEST",
            "secret_access_key": "testsecret123",
            "region_name": "us-east-1",
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
        return self.pipeline.run(resources)


def _execute(ingestion_id):
    from hub.data_movement.ingestion_execution import execute_dlt_ingestion

    return execute_dlt_ingestion(ingestion_id)


class TestFailureClassification:
    """The retry policy classifies failure classes (the rebuilt
    classifier from the dead dlt_retry module)."""

    def test_connection_class_errors_are_retryable(self):
        from hub.data_movement.retry_policy import is_retryable_error

        assert is_retryable_error("Connection timeout after 30s")
        assert is_retryable_error("connection refused")
        assert is_retryable_error("read timed out")

    def test_permanent_classes_are_not_retryable(self):
        from hub.data_movement.retry_policy import is_retryable_error

        assert not is_retryable_error("Schema mismatch: column missing")
        assert not is_retryable_error("Permission denied")
        assert not is_retryable_error("Out of memory: process killed")


class TestBoundedRetry:
    """The live execution retries RETRYABLE failures, bounded."""

    def _patch_discovery(self, monkeypatch):
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda obj: [{"key": "staging/a.csv", "size": 12}],
        )

    @pytest.fixture(autouse=True)
    def _catalog_env(self, monkeypatch, settings):
        settings.CLAMAV_ENABLED = False
        _patch_catalog_env(monkeypatch)

    def test_transient_failure_is_retried_and_the_run_succeeds(self, monkeypatch, tmp_path):
        """The transient-failure-retried evidence pin."""
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)
        dataset_dir = str(tmp_path / "w39_transient")

        calls = {"count": 0}
        handles = []

        def flaky_factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], dataset_dir)
            handles.append(handle)
            original_run = handle.run

            def flaky_run(resources, credentials=None, **_kw):
                calls["count"] += 1
                if calls["count"] == 1:
                    raise ConnectionError("connection refused: warehouse unreachable")
                return original_run(resources, credentials=credentials)

            handle.run = flaky_run
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, flaky_factory):
            outcome = _execute(ingestion.id)

        assert outcome.get("error_message") is None, outcome
        assert outcome["files_processed"] >= 1, "the retry must eventually deliver the load"
        assert outcome.get("retry_count") == 1, "exactly one retry was needed and must be recorded"
        assert calls["count"] == 2, "first attempt + one retry"

    def test_persistent_retryable_failure_is_bounded(self, monkeypatch, tmp_path):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)

        calls = {"count": 0}

        def always_failing_factory(**kwargs):
            handle = _RecordingPipelineHandle(
                kwargs["pipeline_name"], str(tmp_path / "w39_bounded")
            )

            def failing_run(resources, credentials=None, **_kw):
                calls["count"] += 1
                raise ConnectionError("connection refused")

            handle.run = failing_run
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, always_failing_factory):
            outcome = _execute(ingestion.id)

        assert outcome.get("error_message"), "the exhausted retry must surface the error"
        assert outcome["retry_count"] >= 2, "the bound must be at least two retries"
        assert calls["count"] == outcome["retry_count"] + 1, (
            "attempts = retries + 1 — the loop is bounded"
        )

    def test_permanent_failure_is_not_retried(self, monkeypatch, tmp_path):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        self._patch_discovery(monkeypatch)

        calls = {"count": 0}

        def schema_failing_factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], str(tmp_path / "w39_perm"))

            def failing_run(resources, credentials=None, **_kw):
                calls["count"] += 1
                raise ValueError("Schema mismatch: column 'id' missing")

            handle.run = failing_run
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, schema_failing_factory):
            outcome = _execute(ingestion.id)

        assert outcome.get("error_message"), "the permanent failure must surface"
        assert calls["count"] == 1, "a permanent failure must NOT be retried — exactly one attempt"
        assert outcome.get("retry_count") == 0


class TestDlqRetryEffect:
    """Retrying a DLQ item re-queues the file for the LIVE dlt state —
    the next execution re-dispatches it."""

    @pytest.fixture(autouse=True)
    def _catalog_env(self, monkeypatch, settings):
        settings.CLAMAV_ENABLED = False
        _patch_catalog_env(monkeypatch)

    def test_dlq_retry_clears_the_dlt_processed_key_and_redispatches(self, monkeypatch, tmp_path):
        tenant = _mk_tenant()
        ingestion = _mk_ingestion(tenant)
        dataset_dir = str(tmp_path / "w39_dlq_effect")
        pipeline_name = f"ingestion-{ingestion.id}"

        from hub.data_movement.dlt_incremental import get_processed_keys, mark_processed

        # The file was processed in a past successful run (the live
        # state the dlt path really reads).
        mark_processed(pipeline_name, ["staging/a.csv"])
        assert "staging/a.csv" in get_processed_keys(pipeline_name)

        # The operator (or the legacy sync) filed a DLQ item for it.
        from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
        from hub.apps.scheduled_ingestion.models import DeadLetterQueueItem

        dlq_item = DeadLetterQueueItem.objects.create(
            scheduled_ingestion=ingestion,
            file_path="staging/a.csv",
            error_message="Connection timeout",
            error_code="TIMEOUT",
            retry_count=3,
            first_failed_at=__import__("django").utils.timezone.now(),
            last_failed_at=__import__("django").utils.timezone.now(),
            permanently_failed_at=__import__("django").utils.timezone.now(),
            resolution_status="PENDING",
        )

        # Retry the DLQ item — the effect must reach the LIVE state.
        success = DeadLetterQueueManager.retry_file(dlq_item_id=str(dlq_item.id))
        assert success
        assert "staging/a.csv" not in get_processed_keys(pipeline_name), (
            "the retry must clear the dlt processed key — the file is re-queued"
        )

        # The next execution re-dispatches the file for real.
        from hub.data_movement import ingestion_execution

        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda obj: [{"key": "staging/a.csv", "size": 12}],
        )
        handles = []

        def factory(**kwargs):
            handle = _RecordingPipelineHandle(kwargs["pipeline_name"], dataset_dir)
            handles.append(handle)
            return handle

        with mock.patch(_INGESTION_PIPELINE_FACTORY, factory):
            outcome = _execute(ingestion.id)

        assert outcome.get("error_message") is None, outcome
        assert outcome["files_processed"] >= 1, (
            "the DLQ retry effect: the re-queued file was actually re-dispatched"
        )
