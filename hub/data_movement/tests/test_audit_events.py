"""TDD pins for the warehouse movement audit set (openspec
wire-databricks-dlt-movement task 6.9, design D6).

Registration pins: the six event constants exist in the canonical
registry with the name==value convention and ride ``__all__``.

Emission pins (no mocks — real Postgres audit rows through the REAL
entrypoints; the sanctioned seams are the pipeline factory + credential
resolver recording symbols, the 6.5 convention):
  - a completed run writes ONE ``WAREHOUSE_EXPORT_STARTED`` at dispatch
    and ONE ``WAREHOUSE_EXPORT_COMPLETED`` at the terminal (never both
    terminal events),
  - a refused run (pre-flight) writes ONLY the FAILED terminal row —
    it never dispatched,
  - a crashed run writes STARTED + FAILED,
  - the ingestion legs mirror with the ``WAREHOUSE_INTAKE_*`` set,
  - the rows carry the tenant + run attribution,
  - an audit-store failure NEVER blocks the movement (best-effort —
    the run still completes with its real outcome).
"""

import uuid

import pytest

pytestmark = pytest.mark.django_db(transaction=True)

DATABRICKS_DEST = {
    "host": "dbc-abc.cloud.databricks.com",
    "http_path": "/sql/1.0/warehouses/abc123",
    "catalog": "meshant",
    "schema": "staging",
}


@pytest.fixture
def tenant():
    from tests.factories import TenantFactory

    return TenantFactory.create_tenant()


class TestEventRegistration:
    def test_the_six_constants_are_registered_with_the_convention(self):
        from hub.apps.audit import event_types

        for name in (
            "WAREHOUSE_EXPORT_STARTED",
            "WAREHOUSE_EXPORT_COMPLETED",
            "WAREHOUSE_EXPORT_FAILED",
            "WAREHOUSE_INTAKE_STARTED",
            "WAREHOUSE_INTAKE_COMPLETED",
            "WAREHOUSE_INTAKE_FAILED",
        ):
            assert getattr(event_types, name) == name, "the name==value convention"
            assert name in event_types.__all__, f"{name} must ride __all__"


class _RecordingPipeline:
    """The sanctioned factory recorder (the 6.5 convention)."""

    def __init__(self, *, fail: bool = False):
        self.run_calls = 0
        self.run_kwargs: list = []
        self.fail = fail

    def run(self, *args, **kwargs):
        self.run_calls += 1
        self.run_kwargs.append((args, kwargs))
        if self.fail:
            raise RuntimeError("destination down")
        return {"loads": [{"load_id": "l1", "status": "completed"}]}


@pytest.fixture
def recording_stack(monkeypatch):
    from hub.data_movement import export_execution, ingestion_execution

    export_recorder = _RecordingPipeline()
    ingestion_recorder = _RecordingPipeline()

    def export_factory(**kwargs):
        assert set(kwargs) == {"destination_type", "pipeline_name", "credential_ref"}
        return export_recorder

    def ingestion_factory(**kwargs):
        assert set(kwargs) == {"source_type", "pipeline_name", "credential_ref"}
        return ingestion_recorder

    monkeypatch.setattr(export_execution, "create_export_pipeline", export_factory)
    monkeypatch.setattr(export_execution, "resolve_credentials", lambda _ref: {})
    monkeypatch.setattr(ingestion_execution, "create_ingestion_pipeline", ingestion_factory)
    monkeypatch.setattr(ingestion_execution, "resolve_credentials", lambda _ref: {})
    return {"export": export_recorder, "ingestion": ingestion_recorder}


def _asset(tenant):
    from tests.factories import AssetFactory

    return AssetFactory.create(tenant=tenant)


def _contract(tenant, asset, *, validation_status="VALID"):
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


def _export(tenant, source_scope):
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"audit-export-{uuid.uuid4().hex[:8]}",
        destination_type="DATABRICKS_TABLE",
        destination_config=dict(DATABRICKS_DEST),
        source_scope=source_scope,
        schedule_config={"cron": "0 3 * * *"},
        credential_ref="arn:aws:secretsmanager:us-east-1:1:secret:db-creds",
    )


def _ingestion(tenant):
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"audit-ing-{uuid.uuid4().hex[:8]}",
        source_type="S3",
        source_config={"bucket": "test-bucket", "access_key_id": "AKIATEST"},
        schedule_type="DAILY",
        schedule_config={"time": "02:00"},
        file_pattern=".*",
        created_by=None,
    )


def _audit_rows(tenant, *actions):
    from hub.apps.audit.models import AuditEvent

    return list(AuditEvent.objects.filter(tenant=tenant, action__in=actions).order_by("timestamp"))


class TestExportAuditTransitions:
    def _execute(self, export_id):
        from hub.data_movement.export_execution import execute_dlt_export

        return execute_dlt_export(export_id)

    def test_a_completed_run_writes_started_then_completed_once(
        self, tenant, recording_stack, monkeypatch
    ):
        from hub.data_movement import export_execution

        monkeypatch.setattr(
            export_execution, "resolve_credentials", lambda _ref: {"token": "dapi-staging"}
        )
        asset = _asset(tenant)
        _contract(tenant, asset)
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        result = self._execute(export_row.id)

        assert result["error_message"] is None
        rows = _audit_rows(
            tenant,
            "WAREHOUSE_EXPORT_STARTED",
            "WAREHOUSE_EXPORT_COMPLETED",
            "WAREHOUSE_EXPORT_FAILED",
        )
        actions = [row.action for row in rows]
        assert actions == ["WAREHOUSE_EXPORT_STARTED", "WAREHOUSE_EXPORT_COMPLETED"], (
            "one STARTED at dispatch + one COMPLETED at the terminal — never both terminal rows"
        )
        for row in rows:
            assert str(row.resource_id) == str(export_row.id)
            assert row.resource_type == "SCHEDULED_EXPORT"
        assert recording_stack["export"].run_calls == 1

    def test_a_refused_run_writes_only_the_failed_terminal_row(self, tenant, recording_stack):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        result = self._execute(export_row.id)

        assert "EXPORT_CONTRACT_VALIDATION_FAILED" in result["error_message"]
        rows = _audit_rows(
            tenant,
            "WAREHOUSE_EXPORT_STARTED",
            "WAREHOUSE_EXPORT_COMPLETED",
            "WAREHOUSE_EXPORT_FAILED",
        )
        assert [row.action for row in rows] == ["WAREHOUSE_EXPORT_FAILED"], (
            "a refused run never dispatched — no STARTED row, one FAILED terminal row"
        )
        assert recording_stack["export"].run_calls == 0, "the refused run never ran the pipeline"

    def test_a_crashed_run_writes_started_then_failed(self, tenant, recording_stack, monkeypatch):
        from hub.data_movement import export_execution

        monkeypatch.setattr(
            export_execution, "resolve_credentials", lambda _ref: {"token": "dapi-staging"}
        )
        recording_stack["export"].fail = True
        asset = _asset(tenant)
        _contract(tenant, asset)
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        result = self._execute(export_row.id)

        assert "destination down" in result["error_message"]
        rows = _audit_rows(
            tenant,
            "WAREHOUSE_EXPORT_STARTED",
            "WAREHOUSE_EXPORT_COMPLETED",
            "WAREHOUSE_EXPORT_FAILED",
        )
        assert [row.action for row in rows] == [
            "WAREHOUSE_EXPORT_STARTED",
            "WAREHOUSE_EXPORT_FAILED",
        ]
        assert recording_stack["export"].run_calls == 1

    def test_an_audit_store_failure_never_blocks_the_movement(
        self, tenant, recording_stack, monkeypatch
    ):
        from hub.data_movement import export_execution

        monkeypatch.setattr(
            export_execution, "resolve_credentials", lambda _ref: {"token": "dapi-staging"}
        )
        asset = _asset(tenant)
        _contract(tenant, asset)
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        def boom(*args, **kwargs):
            raise RuntimeError(f"audit db down ({len(args)} positional, {len(kwargs)} kw)")

        # A TOTAL outage: both the emitter's bound symbol and the source
        # symbol (the DLT-row path imports it at call time) fail.
        monkeypatch.setattr("hub.data_movement.audit_events.create_audit_event", boom)
        monkeypatch.setattr("hub.apps.audit.utils.create_audit_event", boom)

        result = self._execute(export_row.id)

        assert result["error_message"] is None, "an audit-DB outage must never block the movement"
        assert recording_stack["export"].run_calls == 1


class TestIntakeAuditTransitions:
    def _execute(self, ingestion_id):
        from hub.data_movement.ingestion_execution import execute_dlt_ingestion

        return execute_dlt_ingestion(ingestion_id)

    def test_a_completed_intake_writes_started_then_completed_once(
        self, tenant, recording_stack, monkeypatch, w38_catalog_seams
    ):
        ingestion = _ingestion(tenant)
        from hub.data_movement import ingestion_execution

        # Isolate source discovery: these tests pin the AUDIT transition
        # contract, not the S3 connector (which needs real MinIO creds).
        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda _obj: [{"key": "csv/f1.csv", "name": "f1.csv"}],
        )

        result = self._execute(ingestion.id)

        assert result["error_message"] is None
        rows = _audit_rows(
            tenant,
            "WAREHOUSE_INTAKE_STARTED",
            "WAREHOUSE_INTAKE_COMPLETED",
            "WAREHOUSE_INTAKE_FAILED",
        )
        assert [row.action for row in rows] == [
            "WAREHOUSE_INTAKE_STARTED",
            "WAREHOUSE_INTAKE_COMPLETED",
        ]
        for row in rows:
            assert str(row.resource_id) == str(ingestion.id)
            assert row.resource_type == "SCHEDULED_INGESTION"
        assert recording_stack["ingestion"].run_calls == 1

    def test_a_failed_intake_writes_started_then_failed(self, tenant, recording_stack, monkeypatch):
        recording_stack["ingestion"].fail = True
        ingestion = _ingestion(tenant)

        from hub.data_movement import ingestion_execution

        # Isolate source discovery: these tests pin the AUDIT transition
        # contract, not the S3 connector (which needs real MinIO creds).
        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda _obj: [{"key": "csv/f1.csv", "name": "f1.csv"}],
        )

        result = self._execute(ingestion.id)

        assert "destination down" in result["error_message"]
        rows = _audit_rows(
            tenant,
            "WAREHOUSE_INTAKE_STARTED",
            "WAREHOUSE_INTAKE_COMPLETED",
            "WAREHOUSE_INTAKE_FAILED",
        )
        assert [row.action for row in rows] == [
            "WAREHOUSE_INTAKE_STARTED",
            "WAREHOUSE_INTAKE_FAILED",
        ]

    def test_an_audit_store_failure_never_blocks_the_intake(
        self, tenant, recording_stack, monkeypatch, w38_catalog_seams
    ):
        ingestion = _ingestion(tenant)
        from hub.data_movement import ingestion_execution

        # Isolate source discovery: these tests pin the AUDIT transition
        # contract, not the S3 connector (which needs real MinIO creds).
        monkeypatch.setattr(
            ingestion_execution,
            "_discover_source_files",
            lambda _obj: [{"key": "csv/f1.csv", "name": "f1.csv"}],
        )

        def boom(*args, **kwargs):
            raise RuntimeError(f"audit db down ({len(args)} positional, {len(kwargs)} kw)")

        # A TOTAL outage: both the emitter's bound symbol and the source
        # symbol (the DLT-row path imports it at call time) fail.
        monkeypatch.setattr("hub.data_movement.audit_events.create_audit_event", boom)
        monkeypatch.setattr("hub.apps.audit.utils.create_audit_event", boom)

        result = self._execute(ingestion.id)

        assert result["error_message"] is None
        assert recording_stack["ingestion"].run_calls == 1
