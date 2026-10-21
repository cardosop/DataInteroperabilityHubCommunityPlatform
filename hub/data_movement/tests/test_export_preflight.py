"""TDD pins for the pre-export ODCS contract validation (openspec
wire-databricks-dlt-movement task 6.5).

No mocks: REAL Postgres rows (tenant + asset + contract + export). The
pre-flight is a PURE read — every failure is raised BEFORE any movement
work, and the violation set is aggregated (every offending source is
reported in one classified error, never fail-fast on the first).
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
    tenant, asset, *, validation_status="VALID", spec_type="ODCS", status="ACTIVE", **kwargs
):
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
        **kwargs,
    )


def _export(tenant, source_scope):
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"preflight-{uuid.uuid4().hex[:8]}",
        destination_type="DATABRICKS_TABLE",
        destination_config={
            "host": "dbc-abc.cloud.databricks.com",
            "http_path": "/sql/1.0/warehouses/abc123",
            "catalog": "meshant",
            "schema": "staging",
        },
        source_scope=source_scope,
        schedule_config={"cron": "0 3 * * *"},
    )


def _validate(export_row):
    from hub.data_movement.export_preflight import validate_export_contracts

    return validate_export_contracts(export_row)


class TestValidContractsPass:
    def test_an_active_valid_odcs_contract_passes(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="VALID")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        validated = _validate(export_row)

        assert [c.id for c in validated] == [contract.id]

    def test_a_warning_only_contract_passes(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="WARNING_ONLY")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        validated = _validate(export_row)

        assert [c.id for c in validated] == [contract.id]

    def test_a_contract_id_scope_is_validated_directly(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="VALID")
        export_row = _export(tenant, {"contract_id": str(contract.id)})

        validated = _validate(export_row)

        assert [c.id for c in validated] == [contract.id]

    def test_dataset_scopes_resolve_through_the_dataset_asset(self, tenant):
        from hub.apps.datasets.models import Dataset

        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="VALID")
        dataset = Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            kind="FILE",
            format="PARQUET",
        )
        export_row = _export(tenant, {"dataset_ids": [str(dataset.id)]})

        validated = _validate(export_row)

        assert [c.id for c in validated] == [contract.id]

    def test_a_scope_without_contract_bearing_sources_passes_empty(self, tenant):
        export_row = _export(tenant, {"file_ids": [str(uuid.uuid4())]})

        assert _validate(export_row) == []


class TestInvalidContractsFailClosed:
    def _assert_fails(self, export_row, *, expected_code):
        from hub.data_movement.export_preflight import ExportContractValidationError

        with pytest.raises(ExportContractValidationError) as exc_info:
            _validate(export_row)
        assert exc_info.value.code == expected_code
        return exc_info.value

    def test_an_invalid_contract_fails(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        exc = self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

        assert exc.violations[0]["asset_id"] == str(asset.id)
        assert "INVALID" in exc.violations[0]["reason"]

    def test_an_error_status_contract_fails(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="ERROR")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

    def test_an_unvalidated_contract_fails(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status=None)
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

    def test_a_non_odcs_contract_fails(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID", spec_type="ODPS")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        exc = self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")
        assert "ODPS" in exc.violations[0]["reason"]

    def test_an_asset_without_an_active_contract_fails(self, tenant):
        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="VALID", status="DRAFT")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})

        exc = self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")
        assert "no ACTIVE contract" in exc.violations[0]["reason"]

    def test_a_missing_asset_fails(self, tenant):
        export_row = _export(tenant, {"asset_ids": [str(uuid.uuid4())]})

        self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

    def test_an_invalid_contract_id_scope_fails(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, {"contract_id": str(contract.id)})

        self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

    def test_a_draft_contract_id_scope_fails_even_when_validated(self, tenant):
        asset = _asset(tenant)
        contract = _contract(tenant, asset, validation_status="VALID", status="DRAFT")
        export_row = _export(tenant, {"contract_id": str(contract.id)})

        exc = self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")
        assert len(exc.violations) == 1
        assert "not ACTIVE" in exc.violations[0]["reason"]

    def test_all_violations_are_aggregated_in_one_error(self, tenant):
        bad_asset = _asset(tenant)
        _contract(tenant, bad_asset, validation_status="INVALID")
        missing_contract_asset = _asset(tenant)
        missing_asset_id = str(uuid.uuid4())
        export_row = _export(
            tenant,
            {"asset_ids": [str(bad_asset.id), str(missing_contract_asset.id), missing_asset_id]},
        )

        exc = self._assert_fails(export_row, expected_code="EXPORT_CONTRACT_VALIDATION_FAILED")

        assert len(exc.violations) == 3


class TestPreflightIsPure:
    def test_validation_never_writes_rows(self, tenant):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.contracts.models import Contract
        from hub.data_movement.export_preflight import ExportContractValidationError

        asset = _asset(tenant)
        _contract(tenant, asset, validation_status="INVALID")
        export_row = _export(tenant, {"asset_ids": [str(asset.id)]})
        contracts_before = Contract.objects.filter(tenant=tenant).count()
        audit_before = AuditEvent.objects.filter(tenant=tenant).count()

        with pytest.raises(ExportContractValidationError):
            _validate(export_row)
        # A contract-bearing-free scope validates empty and writes nothing.
        _validate(_export(tenant, {"file_ids": [str(uuid.uuid4())]}))

        assert Contract.objects.filter(tenant=tenant).count() == contracts_before
        assert AuditEvent.objects.filter(tenant=tenant).count() == audit_before
