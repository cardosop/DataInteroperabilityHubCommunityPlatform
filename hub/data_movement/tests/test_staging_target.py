"""TDD pins for the per-tenant staging schema + staging target resolution
(openspec wire-databricks-dlt-movement task 6.5).

No mocks: REAL Postgres tenant rows (the ``databricks_staging_schema_name``
field) and the REAL resolution functions. The staging schema resolves
fail-closed — a UC identifier is required for the tenant override AND the
destination-provided catalog/schema (an invalid identifier is refused
before any movement work).
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
def staging_tenant():
    from tests.factories import TenantFactory

    return TenantFactory.create_tenant()


class TestStagingSchemaResolution:
    def test_blank_override_resolves_to_the_destination_schema(self, staging_tenant):
        from hub.data_movement.staging import staging_schema_for

        assert staging_schema_for(staging_tenant, target_schema="staging") == "staging"

    def test_a_tenant_override_is_respected(self, staging_tenant):
        from hub.data_movement.staging import staging_schema_for

        staging_tenant.databricks_staging_schema_name = "governed_staging"
        assert staging_schema_for(staging_tenant, target_schema="staging") == "governed_staging"

    def test_an_invalid_tenant_override_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused, staging_schema_for

        staging_tenant.databricks_staging_schema_name = "bad schema!"
        with pytest.raises(DatabricksStagingRefused):
            staging_schema_for(staging_tenant, target_schema="staging")

    def test_an_invalid_destination_schema_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused, staging_schema_for

        with pytest.raises(DatabricksStagingRefused):
            staging_schema_for(staging_tenant, target_schema="staging; DROP TABLE x")


class TestStagingTargetResolution:
    def _resolve(self, tenant, dest_config):
        from hub.data_movement.staging import resolve_staging_target

        return resolve_staging_target(tenant, destination_config=dest_config)

    def test_a_valid_config_resolves_the_full_target(self, staging_tenant):
        target = self._resolve(staging_tenant, DATABRICKS_DEST)

        assert target.catalog == "meshant"
        assert target.schema == "staging"
        assert target.volume_name == "_dlt_staging_load_volume"
        assert target.qualified == "meshant.staging._dlt_staging_load_volume"

    def test_the_tenant_volume_override_rides_the_auto_default(self, staging_tenant):
        staging_tenant.databricks_staging_volume_name = "staging_vol"
        target = self._resolve(staging_tenant, DATABRICKS_DEST)

        assert target.volume_name == "staging_vol"
        assert target.qualified == "meshant.staging.staging_vol"

    def test_the_tenant_schema_override_rides_the_destination_schema(self, staging_tenant):
        staging_tenant.databricks_staging_schema_name = "governed_staging"
        target = self._resolve(staging_tenant, DATABRICKS_DEST)

        assert target.schema == "governed_staging"
        assert target.qualified == "meshant.governed_staging._dlt_staging_load_volume"

    def test_a_missing_catalog_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused

        dest = dict(DATABRICKS_DEST)
        del dest["catalog"]
        with pytest.raises(DatabricksStagingRefused):
            self._resolve(staging_tenant, dest)

    def test_a_missing_schema_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused

        dest = dict(DATABRICKS_DEST)
        del dest["schema"]
        with pytest.raises(DatabricksStagingRefused):
            self._resolve(staging_tenant, dest)

    def test_an_invalid_catalog_identifier_is_refused(self, staging_tenant):
        from hub.data_movement.staging import DatabricksStagingRefused

        dest = dict(DATABRICKS_DEST, catalog="meshant.catalog")
        with pytest.raises(DatabricksStagingRefused):
            self._resolve(staging_tenant, dest)


class TestStagingSchemaTenantField:
    def test_the_field_ships_blank_by_default(self, staging_tenant):
        assert staging_tenant.databricks_staging_schema_name == ""

    def test_the_field_persists(self, staging_tenant):
        staging_tenant.databricks_staging_schema_name = "staging_schema_a"
        staging_tenant.save(update_fields=["databricks_staging_schema_name"])
        staging_tenant.refresh_from_db()
        assert staging_tenant.databricks_staging_schema_name == "staging_schema_a"


def _databricks_export(tenant, destination_config=None, source_scope=None):
    from hub.apps.scheduled_export.models import ScheduledExport

    return ScheduledExport.objects.create(
        tenant=tenant,
        name=f"db-export-{uuid.uuid4().hex[:8]}",
        destination_type="DATABRICKS_TABLE",
        destination_config=destination_config or dict(DATABRICKS_DEST),
        source_scope=source_scope or {"asset_ids": [str(uuid.uuid4())]},
        schedule_config={"cron": "0 3 * * *"},
    )
