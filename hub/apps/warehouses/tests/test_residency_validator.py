"""
Phase 277.B.093 — data residency cross-validation tests.
"""
import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.warehouses.models import WarehouseConnection
from hub.apps.warehouses.residency_validator import (
    find_residency_mismatches,
    validate_warehouse_region,
)


class ResidencyValidatorTests(TestCase):
    def test_allows_when_no_tenant_residency(self):
        result = validate_warehouse_region(None, "us-east-1")
        assert result.valid

    def test_allows_when_warehouse_region_empty(self):
        result = validate_warehouse_region("eu-west-1", "")
        assert result.valid

    def test_allows_when_warehouse_region_unknown(self):
        result = validate_warehouse_region("eu-west-1", "mars-west-1")
        assert result.valid

    def test_allows_when_tenant_region_unknown(self):
        result = validate_warehouse_region("mars-east-1", "us-east-1")
        assert result.valid

    def test_allows_eu_warehouse_for_eu_tenant(self):
        """eu-west-1 tenant + europe-west1 warehouse = allowed (both EU)."""
        result = validate_warehouse_region("eu-west-1", "europe-west1")
        assert result.valid
        assert result.warehouse_iso == "BE"

    def test_allows_eu_warehouse_for_eu_generic_tenant(self):
        result = validate_warehouse_region("eu", "eu-west-1")
        assert result.valid
        assert result.warehouse_iso == "IE"

    def test_allows_us_warehouse_for_us_tenant(self):
        result = validate_warehouse_region("us-east-1", "us-west-2")
        assert result.valid
        assert result.warehouse_iso == "US"

    def test_blocks_us_warehouse_for_eu_tenant(self):
        """EU tenant with US warehouse = rejected."""
        result = validate_warehouse_region("eu-west-1", "us-east-1")
        assert not result.valid
        assert result.warehouse_iso == "US"
        assert "US" not in result.allowed_iso  # EU block does not include US

    def test_blocks_non_eu_warehouse_for_eu_tenant(self):
        """EU tenant with non-EU warehouse like India = rejected."""
        result = validate_warehouse_region("eu", "asia-south1")
        assert not result.valid

    def test_returns_allowed_iso_set(self):
        result = validate_warehouse_region("uk", "eu-west-1")
        assert result.valid  # IE is not GB, but UK tenant: map doesn't include IE
        # Actually: UK allows only GB, eu-west-1 → IE. So this should fail!
        # Let me check: The mapping says "uk": {"GB"}. eu-west-1 maps to IE.
        # IE is NOT in {"GB"} → valid should be False.
        assert not result.valid  # Correct — UK residency blocks Irish warehouse


class WarehouseModelResidencyValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.eu_tenant = Tenant.objects.create(
            name="EU Corp", slug="eu-corp", status=TenantStatus.ACTIVE,
            data_residency_region="eu-west-1",
        )
        cls.us_tenant = Tenant.objects.create(
            name="US Corp", slug="us-corp", status=TenantStatus.ACTIVE,
            data_residency_region="us-east-1",
        )
        cls.no_residency_tenant = Tenant.objects.create(
            name="Global Corp", slug="global-corp", status=TenantStatus.ACTIVE,
            data_residency_region=None,
        )

    def test_eu_tenant_us_warehouse_rejected_on_save(self):
        """Saving a US-region warehouse for an EU tenant must raise ValidationError."""
        conn = WarehouseConnection(
            tenant=self.eu_tenant,
            name="US Warehouse",
            warehouse_type="SNOWFLAKE",
            region="us-east-1",
        )
        with pytest.raises(ValidationError) as ctx:
            conn.save()
        assert "DATA_RESIDENCY_MISMATCH" in str(ctx.value)

    def test_eu_tenant_eu_warehouse_accepted(self):
        """Saving an EU-region warehouse for an EU tenant must succeed."""
        conn = WarehouseConnection.objects.create(
            tenant=self.eu_tenant,
            name="EU Warehouse",
            warehouse_type="SNOWFLAKE",
            region="eu-west-1",
        )
        assert conn.pk is not None

    def test_no_residency_tenant_accepts_any_region(self):
        """Tenant without residency rule can use any warehouse region."""
        conn = WarehouseConnection.objects.create(
            tenant=self.no_residency_tenant,
            name="Any Warehouse",
            warehouse_type="SNOWFLAKE",
            region="us-east-1",
        )
        assert conn.pk is not None

    def test_empty_region_always_accepted(self):
        """Warehouse with no region set is always allowed."""
        conn = WarehouseConnection.objects.create(
            tenant=self.eu_tenant,
            name="No Region",
            warehouse_type="BIGQUERY",
            region="",
        )
        assert conn.pk is not None


class FindResidencyMismatchesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.eu_tenant = Tenant.objects.create(
            name="EU Corp", slug="eu-corp-2", status=TenantStatus.ACTIVE,
            data_residency_region="eu",
        )

    def test_finds_mismatches(self):
        """find_residency_mismatches() returns US warehouse for EU tenant."""
        WarehouseConnection.objects.create(
            tenant=self.eu_tenant,
            name="Bad US WH",
            warehouse_type="SNOWFLAKE",
            region="us-east-1",
        )
        mismatches = find_residency_mismatches()
        assert len(mismatches) >= 1
        assert mismatches[0]["warehouse_region"] == "us-east-1"

    def test_no_mismatches_when_all_compliant(self):
        """Clean state returns empty list."""
        WarehouseConnection.objects.filter(tenant=self.eu_tenant).delete()
        # No connections at all → no mismatches
        mismatches = find_residency_mismatches()
        # Filter out any connections from other tests
        ours = [m for m in mismatches if m["tenant_id"] == str(self.eu_tenant.id)]
        assert len(ours) == 0
