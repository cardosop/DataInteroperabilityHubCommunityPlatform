"""TDD pins for the Databricks staging + cost legs (openspec
add-databricks-control-plane Phase 11 task 11.4) — design D4/D5.

- STAGING: artifacts/seeds stage through the workspace's managed UC
  volume — the ``uc.volumes.*`` pins + the NEW ``fs.files.upload`` pin
  (the volume's write surface) on the PINNED production client (never
  a second HTTP stack). The create → use → remove contract: a failed
  stage removes the volume best-effort — the estate is never polluted.
- COST: ONE ``dbt_run`` ledger row per run through the provider-
  agnostic cost-recording seam (the 7.5 inversion) — the exactly-once
  guard is the run row's ``databricks_dbu`` re-checked under
  select_for_update (the 10.6 discipline); stored, not billed. The
  additive ``dbt_run`` source tag rides the P7 ledger's choices.

No mocks: the PRODUCTION client against a REAL threaded local HTTP
server (the wire paths/bodies asserted in order), real Postgres rows,
the REAL cost-recording seam + the registered ledger writer (the
databricks_admin app-ready registration).
"""

import http.server
import json
import threading
import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.databricks_admin.tests._fixtures import require_dns
from hub.apps.databricks_admin.tests._http import RecordingHandler
from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace
from hub.apps.databricks_admin.tests.test_views import _activate_billing
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


def _client(port, tenant_id):
    from hub.apps.databricks_admin.client import DatabricksApiClient

    return DatabricksApiClient(
        base_url=f"http://127.0.0.1:{port}",
        tenant_id=tenant_id,
        credential_config={"token": "dapi-stage"},
        timeout_ms=5000,
        max_retries=1,
        retry_base_delay=0.05,
        retry_max_delay=0.1,
        use_breaker=False,
    )


def _server():
    RecordingHandler.script = []
    RecordingHandler.requests = []
    RecordingHandler.json_script = []
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RecordingHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, port


class TestApiPathPins:
    def test_the_volume_and_files_pins_are_registered(self):
        """The staging surface rides the pinned map — the volume CRUD
        pins (P3) + the NEW fs.files.upload pin (11.4's additive
        volume-write surface), all version-pinned."""
        from hub.apps.databricks_admin import api_paths

        assert api_paths.API_PATHS["uc.volumes.create"] == "/api/2.1/unity-catalog/volumes"
        assert (
            api_paths.API_PATHS["uc.volumes.delete"] == "/api/2.1/unity-catalog/volumes/{full_name}"
        )
        assert api_paths.API_PATHS["fs.files.upload"] == "/api/2.0/fs/files/{path}"
        assert api_paths.API_PATH_VERSIONS["fs.files.upload"] == "2.0"


class TestVolumeStaging(TestCase):
    """The create → use → remove contract on the pinned client."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-stage-{uuid.uuid4().hex[:8]}")

    def _stage(self, client, **kwargs):
        from hub.apps.transformation.databricks_staging import stage_dbt_seeds

        return stage_dbt_seeds(
            client,
            volume_full_name="meshant.default._dbt_staging",
            files={"seeds/customers.csv": b"id,name\n1,Ada\n"},
            **kwargs,
        )

    def test_the_stage_creates_uploads_and_returns_the_paths(self):
        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.json_script = [json.dumps({"name": "_dbt_staging"}), "{}"]

        paths = self._stage(_client(port, str(self.tenant.id)))

        assert paths == ["/Volumes/meshant/default/_dbt_staging/seeds/customers.csv"]
        recorded = RecordingHandler.requests
        assert len(recorded) == 2
        assert recorded[0]["method"] == "POST"
        assert recorded[0]["path"] == "/api/2.1/unity-catalog/volumes"
        assert json.loads(recorded[0]["body"]) == {
            "name": "_dbt_staging",
            "catalog_name": "meshant",
            "schema_name": "default",
            "volume_type": "MANAGED",
        }
        assert recorded[1]["method"] == "PUT"
        assert recorded[1]["path"] == (
            "/api/2.0/fs/files/Volumes/meshant.default._dbt_staging/seeds/customers.csv"
        ), "the WIRE path is the dot-joined full name (the Files API's convention)"
        assert recorded[1]["body"] == "id,name\n1,Ada\n", "the file BYTES ship verbatim"

    def test_a_failed_upload_removes_the_volume(self):
        """The D4 contract: a mid-stage failure removes the partial
        volume — the estate is never polluted."""
        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [200, 500]  # create OK, upload fails
        RecordingHandler.json_script = [json.dumps({"name": "_dbt_staging"}), "{}"]

        from hub.apps.transformation.databricks_staging import DbtStagingError

        with pytest.raises(DbtStagingError, match="upload"):
            self._stage(_client(port, str(self.tenant.id)))

        recorded = RecordingHandler.requests
        assert len(recorded) == 3, "create → failed upload → the cleanup delete"
        assert recorded[2]["method"] == "DELETE"
        assert recorded[2]["path"] == (
            "/api/2.1/unity-catalog/volumes/meshant.default._dbt_staging"
        )

    def test_a_failed_create_raises_with_zero_uploads(self):
        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [400]
        RecordingHandler.json_script = [json.dumps({"error_code": "BAD_REQUEST"})]

        from hub.apps.transformation.databricks_staging import DbtStagingError

        with pytest.raises(DbtStagingError, match="create"):
            self._stage(_client(port, str(self.tenant.id)))
        assert len(RecordingHandler.requests) == 1, "zero uploads, zero cleanup on a failed create"

    def test_remove_is_idempotent(self):
        """A 404 on the cleanup (the volume already gone) is a clean
        estate — never a raised error."""
        server, port = _server()
        self.addCleanup(server.shutdown)
        RecordingHandler.script = [404]
        RecordingHandler.json_script = [json.dumps({"error_code": "NOT_FOUND"})]

        from hub.apps.transformation.databricks_staging import remove_staged_volume

        assert (
            remove_staged_volume(
                _client(port, str(self.tenant.id)),
                volume_full_name="meshant.default._dbt_staging",
            )
            is None
        )
        assert len(RecordingHandler.requests) == 1


class TestDbtRunLedger(TestCase):
    """ONE dbt_run row per run — the 10.6 exactly-once discipline."""

    def setUp(self):
        require_dns()
        self.tenant = TenantFactory.create_tenant()
        _activate_billing(self.tenant)
        self.workspace = _make_workspace(self.tenant, name=f"ws-cost-{uuid.uuid4().hex[:8]}")
        from hub.apps.transformation.models import PipelineExecution, TransformationPipeline

        pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"p-{uuid.uuid4().hex[:8]}",
            pipeline_definition={
                "version": "1.0",
                "steps": [{"name": "s1", "type": "transform"}],
                "nodes": [],
                "connections": [],
            },
        )
        from tests.factories import AssetFactory

        self.source_asset = AssetFactory.create(tenant=self.tenant)
        self.result_asset = AssetFactory.create(tenant=self.tenant)
        self.execution = PipelineExecution.objects.create(
            pipeline=pipeline,
            asset=self.source_asset,
            result_asset=self.result_asset,
            status="COMPLETED",
            started_at=timezone.now() - timedelta(minutes=10),
            completed_at=timezone.now(),
        )

    def test_the_source_tag_is_in_the_vocabulary(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedgerSource

        assert DatabricksCostLedgerSource.DBT_RUN == "dbt_run"

    def test_the_estimate_uses_the_44_heuristic(self):
        from hub.apps.transformation.databricks_cost import estimate_dbt_run_cost

        metrics = estimate_dbt_run_cost(duration_seconds=3600, workers=2, dbh_rate=0.55)
        assert metrics["size_factor"] == 2.0  # 1 + 0.5 x workers
        assert metrics["estimated_cost"] == pytest.approx(1.1)  # 1h x 0.55 x 2.0

    def test_a_completed_run_records_exactly_one_ledger_row(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger
        from hub.apps.transformation.databricks_cost import record_dbt_run_cost

        record_dbt_run_cost(
            self.execution,
            workspace_id=str(self.workspace.id),
            workers=2,
            dbh_rate=0.55,
        )
        self.execution.refresh_from_db()
        assert self.execution.databricks_dbu is not None, (
            "the stored estimate guards the exactly-once"
        )

        rows = list(DatabricksCostLedger.objects.filter(tenant=self.tenant, source="dbt_run"))
        assert len(rows) == 1
        assert str(rows[0].workspace_id) == str(self.workspace.id)
        assert rows[0].meta["run_id"] == str(self.execution.id)

    def test_a_second_record_is_a_noop(self):
        from hub.apps.databricks_admin.models import DatabricksCostLedger
        from hub.apps.transformation.databricks_cost import record_dbt_run_cost

        record_dbt_run_cost(
            self.execution, workspace_id=str(self.workspace.id), workers=2, dbh_rate=0.55
        )
        first_dbu = self.execution.databricks_dbu
        result = record_dbt_run_cost(
            self.execution, workspace_id=str(self.workspace.id), workers=2, dbh_rate=0.55
        )
        assert result["recorded"] is False
        self.execution.refresh_from_db()
        assert self.execution.databricks_dbu == first_dbu
        assert (
            DatabricksCostLedger.objects.filter(tenant=self.tenant, source="dbt_run").count() == 1
        )


class TestTransformationLineage(TestCase):
    """The run's source→result edge through the SANCTIONED patch."""

    def setUp(self):
        self.tenant = TenantFactory.create_tenant()
        from tests.factories import AssetFactory

        self.source_asset = AssetFactory.create(tenant=self.tenant)
        self.result_asset = AssetFactory.create(tenant=self.tenant)
        from hub.apps.transformation.models import PipelineExecution, TransformationPipeline

        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            name=f"lin-{uuid.uuid4().hex[:8]}",
            pipeline_definition={
                "version": "1.0",
                "steps": [{"name": "s1", "type": "transform"}],
                "nodes": [],
                "connections": [],
            },
        )
        self.execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            result_asset=self.result_asset,
            status="COMPLETED",
            started_at=timezone.now() - timedelta(minutes=5),
            completed_at=timezone.now(),
        )

    def _contract(self, asset):
        from hub.apps.contracts.models import Contract

        return Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=1,
            status="ACTIVE",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
            validation_status="VALID",
            hub_contract_json={"info": {"name": f"c-{uuid.uuid4().hex[:6]}"}},
        )

    def test_a_completed_run_writes_the_transformation_edge(self):
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.transformation.databricks_lineage import record_transformation_lineage

        source_contract = self._contract(self.source_asset)
        target_contract = self._contract(self.result_asset)

        result = record_transformation_lineage(self.execution)
        assert result["recorded"] is True

        rows = LineageEdge.objects.filter(
            tenant=self.tenant,
            edge_type="transformation",
            source_contract=source_contract,
            target_contract=target_contract,
            valid_to__isnull=True,
        )
        assert rows.count() == 1
        assert rows[0].transformation_ref == str(self.pipeline.id)
        assert rows[0].job_ref == str(self.execution.id)

    def test_a_second_record_is_a_noop(self):
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.transformation.databricks_lineage import record_transformation_lineage

        self._contract(self.source_asset)
        self._contract(self.result_asset)
        record_transformation_lineage(self.execution)
        result = record_transformation_lineage(self.execution)

        assert result["recorded"] is False
        assert (
            LineageEdge.objects.filter(tenant=self.tenant, edge_type="transformation").count() == 1
        )

    def test_existing_edges_survive_the_full_state_patch(self):
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.transformation.databricks_lineage import record_transformation_lineage

        self._contract(self.source_asset)
        target_contract = self._contract(self.result_asset)
        from hub.apps.contracts.models import Contract

        other = Contract.objects.create(
            tenant=self.tenant,
            asset=self.result_asset,
            version=2,  # a second contract version — the per-asset version uniqueness
            status="ACTIVE",
            original_spec_type="ODCS",
            original_spec_version="3.0.2",
            original_format="JSON",
            original_raw='{"apiVersion": "odcs.io/v3.0.2"}',
            validation_status="VALID",
            hub_contract_json={"info": {"name": f"c-{uuid.uuid4().hex[:6]}"}},
        )
        from hub.apps.contracts.lineage_edit_service import apply_lineage_patch

        pre_existing = {
            "source_contract": str(other.id),
            "target_contract": str(target_contract.id),
            "source_model": "",
            "source_field": "",
            "target_model": "",
            "target_field": "",
            "edge_type": "reference",
            "transformation_ref": "",
            "job_ref": "",
        }
        apply_lineage_patch(contract=target_contract, desired_edges=[pre_existing], user=None)

        record_transformation_lineage(self.execution)

        assert LineageEdge.objects.filter(tenant=self.tenant, edge_type="reference").count() == 1
        assert (
            LineageEdge.objects.filter(tenant=self.tenant, edge_type="transformation").count() == 1
        )

    def test_a_result_without_a_contract_records_nothing(self):
        from hub.apps.contracts.models import LineageEdge
        from hub.apps.transformation.databricks_lineage import record_transformation_lineage

        self._contract(self.source_asset)  # source only — no result contract

        result = record_transformation_lineage(self.execution)
        assert result["recorded"] is False
        assert (
            LineageEdge.objects.filter(tenant=self.tenant, edge_type="transformation").count() == 0
        )
