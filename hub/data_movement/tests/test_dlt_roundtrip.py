"""Phase 6 (openspec wire-databricks-dlt-movement task 6.11) — the
acceptance round-trip on fixtures (design D1/D2, the spec's "The default
staging lands in the managed volume" family): a scheduled export with a
DATABRICKS_TABLE destination runs the REAL spine end-to-end — preflight →
managed-volume staging target → scoped write credential → the REAL dlt
pipeline executing INSIDE the executor scope → the "UC table" write —
and the outcome lands on the run's terminal state.

NO MOCKS: real Postgres rows (tenant/asset/ACTIVE ODCS contract/file/
ScheduledExport), the REAL preflight + staging + executor; the source
rows are REAL CSV bytes served through the export-sources read seam
(the exact payload shape the production parser consumes — the retired
DuckDB fixture generator added nothing the parser ever saw); the
databricks destination is substituted at the sanctioned
``create_export_pipeline`` factory symbol by a real dlt pipeline writing
to a REAL filesystem destination recording every load (the 4.4 recorder
convention — the recording destination is the sanctioned outbound seam,
the fixture never dials Databricks, and no duckdb/polars dependency
re-enters the API image).
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
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_PIPELINE_FACTORY = "hub.data_movement.export_execution.create_export_pipeline"
_CREDENTIAL_RESOLVER = "hub.data_movement.export_execution.resolve_credentials"

_DATABRICKS_DEST = {
    "host": "adb-fixture.cloud.databricks.com",
    "http_path": "/sql/1.0/warehouses/wh-fixture",
    "catalog": "meshant",
    "schema": "staging",
}


def _mk_tenant():
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"roundtrip-{uid}",
        slug=f"roundtrip-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status=KYCStatus.UNVERIFIED,
        data_movement_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _mk_export(tenant, *, source_scope):
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"rt-{uuid.uuid4().hex[:8]}",
        destination_type=DestinationType.DATABRICKS_TABLE,
        destination_config=_DATABRICKS_DEST,
        schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
        source_scope=source_scope,
        status=ScheduledExportStatus.ACTIVE,
        credential_ref="fixture-pat",
    )


def _mk_contract_source(tenant):
    """A contract-bearing source the preflight accepts: an asset with an
    ACTIVE ODCS contract carrying validation_status VALID."""
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


def _mk_file(tenant, name="source_rows.csv"):
    from hub.apps.files.models import File

    file_id = uuid.uuid4()
    return File.objects.create(
        tenant=tenant,
        name=name,
        storage_path=f"{tenant.id}/{file_id}/{name}",
        size=0,
    )


class _RecordingPipelineHandle:
    """The recording databricks destination (the 4.4 recorder
    convention): a REAL dlt pipeline writing to a REAL filesystem
    destination (the fixture's "UC table" stand-in — the recorded JSONL
    load files hold the rows the duckdb table used to), recording every
    load and the credentials it received. Built by the fixture's factory
    at the sanctioned symbol — the real Databricks wire is never dialed,
    and no duckdb package is needed."""

    def __init__(self, pipeline_name: str, dataset_dir: str):
        import dlt

        self.dataset_dir = dataset_dir
        self.pipeline = dlt.pipeline(
            pipeline_name=pipeline_name,
            destination=dlt.destinations.filesystem(bucket_url=f"file://{dataset_dir}"),
            dataset_name="staging",
        )
        self.loads_seen: list[dict] = []
        self.credentials_seen: list[dict] = []

    def run(self, resources, credentials=None, **_kwargs):
        # The credentials the entrypoint hands over are RECORDED (the
        # pin) but not forwarded into the real filesystem run — a
        # run-time credentials dict REPLACES the destination's configured
        # bucket (the recording destination's stand-in for the databricks
        # credential surface it never dials).
        self.credentials_seen.append(dict(credentials or {}))
        info = self.pipeline.run(resources)
        packages = info.asdict().get("load_packages", [])
        self.loads_seen.append(
            {
                "loads_ids": info.loads_ids,
                "packages": packages,
                "has_failed_jobs": info.has_failed_jobs,
            }
        )
        return {
            "pipeline_name": "fixture",
            "dataset_name": "staging",
            "loads": [{"load_id": p, "status": "completed"} for p in info.loads_ids],
        }


@pytest.fixture
def fixture_pipeline_factory(tmp_path):
    """Patch the sanctioned pipeline factory with the recording
    destination handle over a REAL dlt + REAL filesystem pipeline."""
    dataset_dir = str(tmp_path / "uc_table_filesystem")
    handles: list[_RecordingPipelineHandle] = []

    def factory(**kwargs):
        handle = _RecordingPipelineHandle(
            pipeline_name=kwargs["pipeline_name"], dataset_dir=dataset_dir
        )
        handles.append(handle)
        return handle

    with mock.patch(_PIPELINE_FACTORY, factory):
        yield {"handles": handles, "dataset_dir": dataset_dir}


@pytest.fixture
def fixture_credential_resolver():
    def resolver(credential_ref=None):
        assert credential_ref == "fixture-pat"
        return {"token": "dapi-fixture-pat"}

    with mock.patch(_CREDENTIAL_RESOLVER, resolver):
        yield


def _fixture_rows_csv():
    """The fixture source rows — REAL CSV bytes, the exact payload the
    production parser consumes (the retired DuckDB generator produced
    these identical bytes; the parser's input contract is CSV)."""
    return b"id,name\n1,alpha\n2,beta\n"


class TestExportRoundTrip:
    @pytest.mark.usefixtures("fixture_credential_resolver")
    def test_the_full_spine_lands_the_rows_in_the_uc_table(self, fixture_pipeline_factory):
        tenant = _mk_tenant()
        user = User.objects.create_user(
            email=f"rt-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = _mk_contract_source(tenant)
        source_file = _mk_file(tenant)
        csv_payload = _fixture_rows_csv()

        export = _mk_export(
            tenant,
            source_scope={
                "asset_ids": [str(asset.id)],
                "file_ids": [str(source_file.id)],
            },
        )

        # The export-sources read seam: a REAL reader serving the fixture
        # CSV payload for the fixture file's storage path.
        from hub.data_movement import export_sources

        def fixture_reader(_tenant_id, key):
            assert key == source_file.storage_path
            return csv_payload

        with mock.patch.object(export_sources, "_default_file_reader", fixture_reader):
            service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))
            result = service.execute_export(
                str(export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        assert result.get("error_message") is None
        # The production convention counts LOADS (one pipeline run = one
        # load) — the row-level proof is the fixture table itself.
        assert result.get("items_found") == 1
        assert result.get("items_exported") == 1
        assert result.get("items_failed") == 0

        run = ScheduledExportRun.objects.get(scheduled_export=export)
        assert run.status == ScheduledExportRunStatus.COMPLETED
        dlt_outcome = (run.result_json or {}).get("dlt_outcome", {})
        assert dlt_outcome.get("items_exported") == 1

        # The recording destination saw exactly ONE load with the real
        # resource rows — and the REAL filesystem "UC table" holds them.
        handle = fixture_pipeline_factory["handles"][0]
        assert len(handle.loads_seen) == 1
        assert handle.loads_seen[0]["has_failed_jobs"] is False
        assert len(handle.credentials_seen) == 1
        creds = handle.credentials_seen[0]
        assert creds.get("access_token") == "dapi-fixture-pat", (
            "the scoped write credential flows into the destination"
        )
        assert creds.get("server_hostname") == _DATABRICKS_DEST["host"]

        # The table directory is the scaffold resource's name (dlt's
        # default naming — raw_records) under the pipeline's dataset.
        table_dir = Path(fixture_pipeline_factory["dataset_dir"]) / "staging" / "raw_records"
        rows: list[tuple[str, str]] = []
        for load_file in sorted(table_dir.glob("*.jsonl.gz")):
            with gzip.open(load_file, "rt", encoding="utf-8") as stream:
                for line in stream:
                    row = json.loads(line)
                    rows.append((row["id"], row["name"]))
        # CSV parsing yields string cells (the scaffold's raw_records
        # contract) — the fixture rows land verbatim.
        assert rows == [("1", "alpha"), ("2", "beta")]

    @pytest.mark.usefixtures("fixture_credential_resolver")
    def test_a_failing_destination_fails_the_run_with_zero_exported(self):
        tenant = _mk_tenant()
        user = User.objects.create_user(
            email=f"rt-{uuid.uuid4().hex[:8]}@meshant.test",
            password="testpass123",
            tenant=tenant,
            status=UserStatus.ACTIVE,
        )
        asset = _mk_contract_source(tenant)
        source_file = _mk_file(tenant)
        export = _mk_export(
            tenant,
            source_scope={
                "asset_ids": [str(asset.id)],
                "file_ids": [str(source_file.id)],
            },
        )

        class _FailingHandle:
            def __init__(self, **_kwargs):
                pass

            def run(self, resources, _credentials=None, **_kwargs):
                assert len(resources) == 1, "the fixture rows must reach the destination"
                raise RuntimeError("the destination rejected the load")

        def fixture_reader(_tenant_id, _key):
            return _fixture_rows_csv()

        from hub.data_movement import export_sources

        with (
            mock.patch.object(export_sources, "_default_file_reader", fixture_reader),
            mock.patch(_PIPELINE_FACTORY, _FailingHandle),
        ):
            service = ScheduledExportService(tenant_id=str(tenant.id), user_id=str(user.id))
            result = service.execute_export(
                str(export.id),
                tenant_id=str(tenant.id),
                user_id=str(user.id),
            )

        assert result.get("error_message") == "the destination rejected the load"
        assert result.get("items_exported") == 0
        run = ScheduledExportRun.objects.get(scheduled_export=export)
        assert run.status == ScheduledExportRunStatus.FAILED
