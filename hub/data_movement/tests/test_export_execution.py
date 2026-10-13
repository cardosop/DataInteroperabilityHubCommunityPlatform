"""TDD pins for the export entrypoint wiring (openspec
wire-databricks-dlt-movement task 6.5): the ODCS pre-flight runs BEFORE
any movement work (an invalid contract fails with ZERO side effects),
the staging target + scoped write credential gate the Databricks path
fail-closed, and the pipeline.run executes INSIDE the guard scope.

Real everything except the sanctioned module-symbol seams (the 4.4/5.3
convention): the ``create_export_pipeline`` + ``resolve_credentials``
symbols on the ``export_execution`` module are replaced with recording
REAL objects — the pins assert the call ORDER and the scope contract.
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


class _RecordingPipeline:
    """A REAL minimal pipeline standing in for the dlt pipeline at the
    sanctioned factory symbol. Its run() asserts the guard-bypass
    contract from INSIDE the run — the pipeline execution context."""

    def __init__(self):
        self.run_calls = 0
        self.run_kwargs: list[dict] = []

    def run(self, **kwargs):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        self.run_calls += 1
        self.run_kwargs.append(kwargs)
        ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")
        return {"loads": [{"load_id": "l1", "status": "completed"}]}


@pytest.fixture
def recording_pipeline(monkeypatch):
    from hub.data_movement import export_execution

    recorder = _RecordingPipeline()

    def factory(**kwargs):
        # The pin: the entrypoint hands the production kwargs through.
        assert set(kwargs) == {"destination_type", "pipeline_name", "credential_ref"}
        return recorder

    monkeypatch.setattr(export_execution, "create_export_pipeline", factory)
    return recorder


@pytest.fixture
def recording_credentials(monkeypatch):
    from hub.data_movement import export_execution

    calls: list = []

    def resolver(credential_ref=None):
        calls.append(credential_ref)
        return {}

    monkeypatch.setattr(export_execution, "resolve_credentials", resolver)
    return calls


def _asset(tenant):
    from tests.factories import AssetFactory

    return AssetFactory.create(tenant=tenant)


def _contract(tenant, asset, *, validation_status="VALID", spec_type="ODCS", status="ACTIVE"):
    from hub.apps.contracts.models import Contract

    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        status=status,
        original_spec_type=spec_type,
        original_spec_version="3.0.2",
        original_format="JSON",
        original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
        validation_status=validation_status,
    )


def _export(
    tenant,
    *,
    destination_type="DATABRICKS_TABLE",
    destination_config=None,
    source_scope=None,
    credential_ref=None,
):
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"exec-{uuid.uuid4().hex[:8]}",
        destination_type=destination_type,
        destination_config=destination_config
        or (
            DATABRICKS_DEST
            if destination_type == "DATABRICKS_TABLE"
            else {"bucket": "test-bucket", "access_key_id": "AKIATEST"}
        ),
        source_scope=source_scope,
        schedule_config={"cron": "0 3 * * *"},
        credential_ref=credential_ref,
    )


def _execute(export_id):
    from hub.data_movement.export_execution import execute_dlt_export

    return execute_dlt_export(export_id)


def _audit_rows(tenant, action="DLT_EXPORT_COMPLETED"):
    from hub.apps.audit.models import AuditEvent

    return list(AuditEvent.objects.filter(tenant=tenant, action=action).order_by("timestamp"))


class TestPreFlightFailsWithZeroSideEffects:
    def test_an_invalid_contract_fails_before_any_work(
        self, tenant, recording_pipeline, recording_credentials
    ):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, source_scope={"asset_ids": [str(asset.id)]})

        result = _execute(export_row.id)

        assert result["items_found"] == 0
        assert result["items_exported"] == 0
        assert result["items_failed"] == 0
        assert "EXPORT_CONTRACT_VALIDATION_FAILED" in result["error_message"]
        assert recording_pipeline.run_calls == 0, "no pipeline may be created or run"
        assert recording_credentials == [], "no credential resolution may happen"

    def test_the_failure_audit_row_carries_the_classified_code(
        self, tenant, recording_pipeline, recording_credentials
    ):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, source_scope={"asset_ids": [str(asset.id)]})

        _execute(export_row.id)

        rows = _audit_rows(tenant)
        assert len(rows) == 1
        assert rows[0].result == "FAILURE"
        assert "EXPORT_CONTRACT_VALIDATION_FAILED" in (rows[0].details_json or {}).get(
            "error_message", ""
        )
        assert recording_pipeline.run_calls == 0
        assert recording_credentials == []


class TestStagingAndCredentialGates:
    def test_an_invalid_staging_catalog_fails_before_any_work(
        self, tenant, recording_pipeline, recording_credentials
    ):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        export_row = _export(
            tenant,
            destination_config=dict(DATABRICKS_DEST, catalog="meshant.catalog"),
            source_scope={"asset_ids": [str(asset.id)]},
        )

        result = _execute(export_row.id)

        assert "DLT_STAGING_REFUSED" in result["error_message"]
        assert recording_pipeline.run_calls == 0
        assert recording_credentials == [], "a refused target stops the run before credential work"

    def test_a_databricks_export_without_a_scoped_credential_fails_closed(
        self, tenant, recording_pipeline, recording_credentials
    ):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        export_row = _export(tenant, source_scope={"asset_ids": [str(asset.id)]})

        result = _execute(export_row.id)

        assert "DLT_CREDENTIAL_NOT_RESOLVED" in result["error_message"]
        assert recording_pipeline.run_calls == 0
        assert recording_credentials == [], "no credential_ref — the resolver is never consulted"

    def test_an_m2m_shaped_credential_without_material_fails_closed(
        self, tenant, recording_pipeline, monkeypatch
    ):
        from hub.data_movement import export_execution

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        export_row = _export(
            tenant,
            source_scope={"asset_ids": [str(asset.id)]},
            credential_ref="arn:aws:secretsmanager:us-east-1:1:secret:db-creds",
        )
        monkeypatch.setattr(
            export_execution,
            "resolve_credentials",
            lambda _ref: {"client_id": "svc", "client_secret": "shh"},
        )

        result = _execute(export_row.id)

        assert "DLT_CREDENTIAL_NOT_RESOLVED" in result["error_message"]
        assert recording_pipeline.run_calls == 0


class TestPipelineRunsInsideTheGuardScope:
    def test_a_valid_databricks_export_runs_inside_the_scope(
        self, tenant, recording_pipeline, monkeypatch
    ):
        from hub.data_movement import export_execution
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        export_row = _export(
            tenant,
            source_scope={"asset_ids": [str(asset.id)]},
            credential_ref="arn:aws:secretsmanager:us-east-1:1:secret:db-creds",
        )
        monkeypatch.setattr(
            export_execution,
            "resolve_credentials",
            lambda _ref: {"token": "dapi-staging"},
        )

        result = _execute(export_row.id)

        assert result["error_message"] is None
        assert result["items_exported"] == 1
        assert recording_pipeline.run_calls == 1
        # 6.11 — the destination credentials carry the mapped dest_config
        # (server_hostname/http_path/catalog) + the normalized
        # access_token alongside the resolved material.
        assert recording_pipeline.run_kwargs[0]["credentials"] == {
            "token": "dapi-staging",
            "server_hostname": "dbc-abc.cloud.databricks.com",
            "http_path": "/sql/1.0/warehouses/abc123",
            "catalog": "meshant",
            "access_token": "dapi-staging",
        }

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")

    def test_a_non_databricks_export_keeps_the_legacy_path_inside_the_scope(
        self, tenant, recording_pipeline
    ):
        from hub.data_movement.warehouse_query_runner import ReadOnlyGuard

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        export_row = _export(
            tenant,
            destination_type="S3",
            source_scope={"asset_ids": [str(asset.id)]},
        )

        result = _execute(export_row.id)

        assert result["error_message"] is None
        assert recording_pipeline.run_calls == 1

        with pytest.raises(ValueError, match="not allowed"):
            ReadOnlyGuard.check("INSERT INTO staging.t VALUES (1)")


class TestAssetScopeSourceExpansion:
    """6.11 — an ``asset_ids`` scope exports the files backing the
    assets' datasets (JOURNEY-EXPORT-001: the UI submits asset ids and
    the execution previously yielded ZERO sources — a false-success
    export that touched nothing)."""

    def _file(self, tenant, name="e2e-export.csv"):
        from hub.apps.files.models import File

        return File.objects.create(
            tenant=tenant,
            name=name,
            content_type="text/csv",
            size=12,
            storage_path=f"s3://e2e-bucket/{name}",
            status="ACTIVE",
        )

    def _dataset(self, tenant, asset, file_row):
        from hub.apps.datasets.models import Dataset

        return Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            file=file_row,
            schema_json={"columns": ["id"]},
        )

    def test_asset_scope_yields_the_files_of_the_assets_datasets(self, tenant):
        from hub.data_movement.export_sources import export_rows

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        file_row = self._file(tenant)
        self._dataset(tenant, asset, file_row)
        export_row = _export(
            tenant,
            destination_type="S3",
            source_scope={"asset_ids": [str(asset.id)]},
        )

        rows = list(
            export_rows(
                export_row, read_source=lambda _tenant_id, key: f"content-of-{key}".encode()
            )
        )

        assert rows == [
            ("s3://e2e-bucket/e2e-export.csv", "csv", b"content-of-s3://e2e-bucket/e2e-export.csv")
        ]

    def test_foreign_asset_files_are_never_read(self, tenant):
        from hub.data_movement.export_sources import export_rows
        from tests.factories import TenantFactory

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID")
        other_tenant = TenantFactory.create_tenant()
        foreign_asset = _asset(other_tenant)
        self._dataset(other_tenant, foreign_asset, self._file(other_tenant))
        export_row = _export(
            tenant,
            destination_type="S3",
            source_scope={"asset_ids": [str(asset.id)]},
        )

        rows = list(export_rows(export_row, read_source=lambda _tenant_id, key: b"content"))

        assert rows == []
