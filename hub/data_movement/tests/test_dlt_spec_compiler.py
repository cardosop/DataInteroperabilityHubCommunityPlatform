"""TDD pins for the Hub-config → DLT-spec mapping compiler (openspec
add-databricks-dlt-pipelines task 10.5).

The compiler maps Hub movement configs (ScheduledIngestion
DATABRICKS_SOURCE / ScheduledExport DATABRICKS_TABLE / transformation
pipelines) into DLT pipeline spec DRAFTS (the design D5 compile, never
executes): the target catalog/schema, the target tables/views, and the
source contract's ODCS quality rules as DLT `expect` clauses. The
refusal discipline is the 6.5 pre-flight's:

- a source whose contract fails validation REFUSES with ZERO spec
  emitted (the SAME `ExportContractValidationError` the movement
  pre-flight raises — the validation is REUSED, not reimplemented),
- a config bit the mapping cannot represent REFUSES with
  `DltSpecCompileError` NAMING the bit — never a spec with the setting
  silently absent,
- an unknown ODCS rule severity (or a rule without an expression)
  REFUSES naming the rule — never a silently mapped expectation.

The emitted spec is a REVIEW document (the settings-level pieces the
10.4 create chain will allowlist): stored on the pipeline row by the
caller — the pins prove the round-trip through the real 10.2 model's
`settings` JSONField.

No mocks: REAL Postgres rows (tenant + asset + contract + configs) —
the 313full contract. The P6 movement spine's behavior is unchanged:
the compiler consumes the pre-flight, never the movement executor.
"""

import uuid

import pytest

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def tenant():
    from tests.factories import TenantFactory

    return TenantFactory.create_tenant()


def _asset(tenant, **kwargs):
    from tests.factories import AssetFactory

    return AssetFactory.create(tenant=tenant, **kwargs)


def _contract(
    tenant,
    asset,
    *,
    validation_status="VALID",
    spec_type="ODCS",
    status="ACTIVE",
    rules=None,
    **kwargs,
):
    from hub.apps.contracts.models import Contract

    hub_json = kwargs.pop("hub_contract_json", None)
    if hub_json is None and rules is not None:
        hub_json = {"info": {"name": "test-contract"}, "quality": {"rules": rules}}
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
        hub_contract_json=hub_json,
        **kwargs,
    )


def _export(tenant, source_scope, *, destination_type="DATABRICKS_TABLE", **dest_overrides):
    from hub.apps.scheduled_export.models import ScheduledExport

    destination_config = {
        "host": "dbc-abc.cloud.databricks.com",
        "http_path": "/sql/1.0/warehouses/abc123",
        "catalog": "meshant",
        "schema": "staging",
        **dest_overrides,
    }
    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"spec-export-{uuid.uuid4().hex[:8]}",
        destination_type=destination_type,
        destination_config=destination_config,
        source_scope=source_scope,
        schedule_config={"cron": "0 3 * * *"},
        credential_ref="arn:aws:secretsmanager:us-east-1:1:secret:db-creds",
    )


def _ingestion(
    tenant, contract=None, asset=None, *, source_type="DATABRICKS_SOURCE", **cfg_overrides
):
    from hub.apps.scheduled_ingestion.models import ScheduledIngestion

    source_config = {
        "host": "dbc-abc.cloud.databricks.com",
        "http_path": "/sql/1.0/warehouses/abc123",
        "warehouse_connection_id": "wc-1",
        "catalog": "meshant",
        "schema": "raw",
        "table": "customers",
        "cursor_field": "updated_at",
        **cfg_overrides,
    }
    return ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"spec-ing-{uuid.uuid4().hex[:8]}",
        source_type=source_type,
        source_config=source_config,
        schedule_type="DAILY",
        schedule_config={"cron": "0 3 * * *"},
        contract=contract,
        asset=asset,
    )


def _transformation(tenant, name="spec-xform", **overrides):
    from hub.apps.transformation.models import TransformationPipeline

    return TransformationPipeline.objects.create(
        tenant=tenant,
        name=f"{name}-{uuid.uuid4().hex[:8]}",
        pipeline_definition={
            "version": "1.0",
            "steps": [{"name": "s1", "type": "transform"}],
            "nodes": [],
            "connections": [],
        },
        **overrides,
    )


def _quality_rules():
    return [
        {
            "name": "no_nulls_customer_id",
            "expression": "customer_id IS NOT NULL",
            "severity": "error",
        },
        {
            "name": "positive_amount",
            "expression": "amount > 0",
            "severity": "warn",
        },
    ]


class TestExportCompile:
    def test_an_export_config_compiles_to_a_dlt_spec(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, rules=_quality_rules())
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.dlt_spec_compiler import compile_export_to_dlt_spec

        spec = compile_export_to_dlt_spec(export)

        assert spec["kind"] == "dlt_pipeline_spec_draft"
        assert spec["schema_version"] == 1
        assert spec["name"] == export.name
        assert spec["catalog"] == "meshant"
        assert spec["target"] == "staging"
        assert spec["continuous"] is False
        assert spec["development"] is False
        assert spec["channel"] == "CURRENT"
        assert spec["sources"] == [{"asset_id": str(asset.id)}]
        assert spec["expectations"] == [
            {
                "name": "no_nulls_customer_id",
                "expression": "customer_id IS NOT NULL",
                "action": "fail",
            },
            {"name": "positive_amount", "expression": "amount > 0", "action": "warn"},
        ], "the contract's quality rules become DLT expect clauses (error→fail, warn→warn)"

    def test_the_spec_round_trips_into_the_pipeline_row(self, tenant):
        from hub.apps.databricks_admin.tests._fixtures import require_dns

        require_dns()
        asset = _asset(tenant)
        _contract(tenant, asset, rules=_quality_rules())
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.dlt_spec_compiler import compile_export_to_dlt_spec

        spec = compile_export_to_dlt_spec(export)

        # The caller stores the review document on the pipeline row (the
        # 10.2 model's settings JSONField) — the round-trip must be
        # lossless through the real model.
        # The 1.12 fixture convention: the REAL_HOST constant + the
        # require_dns-guarded creation path (the SSRF guard resolves the
        # host — a fabricated hostname refuses).
        from hub.apps.databricks_admin.models import DatabricksDltPipeline
        from hub.apps.databricks_admin.tests.test_uc_sync import _make_workspace

        workspace = _make_workspace(tenant, name=f"ws-{uuid.uuid4().hex[:8]}")
        row = DatabricksDltPipeline.objects.create(
            workspace=workspace,
            pipeline_id=f"draft-{uuid.uuid4().hex[:8]}",
            name=spec["name"],
            state="IDLE",
            settings=spec,
        )
        assert row.settings == spec, "the emitted spec stores losslessly on the pipeline row"

    def test_an_invalid_source_contract_refuses_with_zero_spec(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.dlt_spec_compiler import compile_export_to_dlt_spec
        from hub.data_movement.export_preflight import ExportContractValidationError

        with pytest.raises(ExportContractValidationError) as excinfo:
            compile_export_to_dlt_spec(export)
        assert any("INVALID" in v["reason"] for v in excinfo.value.violations), (
            "the SAME classified error the 6.5 pre-flight raises — the "
            "validation is reused, never reimplemented"
        )

    def test_an_unmappable_destination_bit_refuses_naming_the_bit(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset)
        export = _export(tenant, {"asset_ids": [str(asset.id)]}, staging_volume="vol-x")

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_export_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_export_to_dlt_spec(export)
        assert "staging_volume" in str(excinfo.value), (
            "the refusal NAMES the unmappable config bit — never a silently dropped setting"
        )

    def test_a_non_databricks_destination_refuses_naming_the_type(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset)
        export = _export(tenant, {"asset_ids": [str(asset.id)]}, destination_type="S3")

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_export_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_export_to_dlt_spec(export)
        assert "S3" in str(excinfo.value)


class TestIngestionCompile:
    def test_an_ingestion_config_compiles_to_a_dlt_spec(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, rules=_quality_rules())
        ingestion = _ingestion(tenant, contract=contract)

        from hub.data_movement.dlt_spec_compiler import compile_ingestion_to_dlt_spec

        spec = compile_ingestion_to_dlt_spec(ingestion)

        assert spec["name"] == ingestion.name
        assert spec["catalog"] == "meshant"
        assert spec["target"] == "raw"
        assert spec["tables"] == [{"name": "customers", "kind": "table"}], (
            "the source table becomes the pipeline's target table"
        )
        assert spec["expectations"] == [
            {
                "name": "no_nulls_customer_id",
                "expression": "customer_id IS NOT NULL",
                "action": "fail",
            },
            {"name": "positive_amount", "expression": "amount > 0", "action": "warn"},
        ]

    def test_a_missing_contract_refuses(self, tenant):
        ingestion = _ingestion(tenant, contract=None, asset=None)

        from hub.data_movement.dlt_spec_compiler import compile_ingestion_to_dlt_spec
        from hub.data_movement.export_preflight import ExportContractValidationError

        with pytest.raises(ExportContractValidationError):
            compile_ingestion_to_dlt_spec(ingestion)

    def test_a_non_databricks_source_refuses_naming_the_type(self, tenant):
        ingestion = _ingestion(tenant, source_type="S3")

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_ingestion_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_ingestion_to_dlt_spec(ingestion)
        assert "S3" in str(excinfo.value)

    def test_a_missing_source_table_refuses(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset)
        ingestion = _ingestion(tenant, contract=contract, table="")

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_ingestion_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_ingestion_to_dlt_spec(ingestion)
        assert "table" in str(excinfo.value)

    def test_an_unmappable_source_bit_refuses_naming_the_bit(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset)
        ingestion = _ingestion(tenant, contract=contract, oauth_scope="all-apis")

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_ingestion_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_ingestion_to_dlt_spec(ingestion)
        assert "oauth_scope" in str(excinfo.value)


class TestTransformationCompile:
    def _pipeline_with_output(self, tenant, target_table="gold_customers"):
        from hub.apps.transformation.models import TransformationNode

        pipeline = _transformation(tenant)
        TransformationNode.objects.create(
            pipeline=pipeline,
            node_type="transform",
            node_config={"expression": "SELECT * FROM src"},
            position={"x": 0, "y": 0},
            order=0,
        )
        TransformationNode.objects.create(
            pipeline=pipeline,
            node_type="output",
            node_config={"target": target_table, "target_schema": "gold"},
            position={"x": 1, "y": 0},
            order=1,
        )
        return pipeline

    def test_a_transformation_compiles_to_a_dlt_spec(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, rules=_quality_rules())
        pipeline = self._pipeline_with_output(tenant)
        pipeline.metadata = {"source_assets": [str(asset.id)]}
        pipeline.save(update_fields=["metadata"])

        from hub.data_movement.dlt_spec_compiler import compile_transformation_to_dlt_spec

        spec = compile_transformation_to_dlt_spec(pipeline)

        assert spec["name"] == pipeline.name
        assert spec["tables"] == [{"name": "gold_customers", "kind": "table"}], (
            "the output node's target becomes the pipeline's target table"
        )
        assert spec["target"] == "gold"
        assert spec["sources"] == [{"asset_id": str(asset.id)}]
        assert spec["expectations"] == [
            {
                "name": "no_nulls_customer_id",
                "expression": "customer_id IS NOT NULL",
                "action": "fail",
            },
            {"name": "positive_amount", "expression": "amount > 0", "action": "warn"},
        ]

    def test_an_unknown_node_kind_refuses(self, tenant):
        from hub.apps.transformation.models import TransformationNode

        pipeline = _transformation(tenant)
        TransformationNode.objects.create(
            pipeline=pipeline,
            node_type="warp_drive",
            node_config={},
            position={"x": 0, "y": 0},
            order=0,
        )

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_transformation_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_transformation_to_dlt_spec(pipeline)
        assert "warp_drive" in str(excinfo.value)

    def test_an_output_node_without_a_target_refuses(self, tenant):
        from hub.apps.transformation.models import TransformationNode

        pipeline = _transformation(tenant)
        TransformationNode.objects.create(
            pipeline=pipeline,
            node_type="output",
            node_config={},
            position={"x": 0, "y": 0},
            order=0,
        )

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_transformation_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_transformation_to_dlt_spec(pipeline)
        assert "output" in str(excinfo.value)


class TestRuleMapping:
    def test_a_rule_without_an_expression_refuses(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, rules=[{"name": "half_rule", "severity": "error"}])
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_export_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_export_to_dlt_spec(export)
        assert "half_rule" in str(excinfo.value), (
            "a rule that cannot become an expect clause refuses — never silently dropped"
        )

    def test_an_unknown_severity_refuses(self, tenant):
        asset = _asset(tenant)
        _contract(
            tenant,
            asset,
            rules=[{"name": "odd_rule", "expression": "x > 0", "severity": "critical"}],
        )
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.dlt_spec_compiler import (
            DltSpecCompileError,
            compile_export_to_dlt_spec,
        )

        with pytest.raises(DltSpecCompileError) as excinfo:
            compile_export_to_dlt_spec(export)
        assert "critical" in str(excinfo.value)


class TestP6SpineUnchanged:
    def test_the_preflight_still_validates_the_export_scope(self, tenant):
        # The compiler REUSES the 6.5 pre-flight — this pin proves the
        # spine's behavior is unchanged: the pre-flight alone still
        # refuses the invalid scope with its aggregated error.
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="ERROR")
        export = _export(tenant, {"asset_ids": [str(asset.id)]})

        from hub.data_movement.export_preflight import (
            ExportContractValidationError,
            validate_export_contracts,
        )

        with pytest.raises(ExportContractValidationError) as excinfo:
            validate_export_contracts(export)
        assert len(excinfo.value.violations) == 1
