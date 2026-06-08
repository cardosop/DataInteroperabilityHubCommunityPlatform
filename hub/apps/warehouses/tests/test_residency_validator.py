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
        """UK tenant with Irish warehouse (eu-west-1) is REJECTED.
        UK allows only GB; eu-west-1 maps to IE → no match."""
        result = validate_warehouse_region("uk", "eu-west-1")
        assert not result.valid
        assert result.warehouse_iso == "IE"
        assert result.allowed_iso == {"GB"}


class WarehouseModelResidencyValidationTests(TestCase):
    def setUp(self):
        import uuid
        _uid = lambda: uuid.uuid4().hex[:8]
        self.eu_tenant = Tenant.objects.create(
            name=f"EU Corp {_uid()}", slug=f"eu-corp-{_uid()}", status=TenantStatus.ACTIVE,
            data_residency_region="eu-west-1",
        )
        self.us_tenant = Tenant.objects.create(
            name=f"US Corp {_uid()}", slug=f"us-corp-{_uid()}", status=TenantStatus.ACTIVE,
            data_residency_region="us-east-1",
        )
        self.no_residency_tenant = Tenant.objects.create(
            name=f"Global Corp {_uid()}", slug=f"global-corp-{_uid()}", status=TenantStatus.ACTIVE,
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
        assert "not compatible" in str(ctx.value) or "region" in str(ctx.value).lower()

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
    def setUp(self):
        import uuid
        _uid = uuid.uuid4().hex[:8]
        self.eu_tenant = Tenant.objects.create(
            name=f"EU Corp {_uid}", slug=f"eu-corp-{_uid}", status=TenantStatus.ACTIVE,
            data_residency_region="eu",
        )

    def test_finds_mismatches(self):
        """find_residency_mismatches() returns empty for clean tenant state."""
        # Create a compatible warehouse (EU tenant + EU region).
        WarehouseConnection.objects.create(
            tenant=self.eu_tenant,
            name="Good EU WH",
            warehouse_type="SNOWFLAKE",
            region="eu-west-1",
        )
        mismatches = find_residency_mismatches()
        ours = [m for m in mismatches if m["tenant_id"] == str(self.eu_tenant.id)]
        assert len(ours) == 0, f"Expected 0 mismatches, got {len(ours)}"

    def test_no_mismatches_when_all_compliant(self):
        """Clean state returns empty list."""
        WarehouseConnection.objects.filter(tenant=self.eu_tenant).delete()
        # No connections at all → no mismatches
        mismatches = find_residency_mismatches()
        # Filter out any connections from other tests
        ours = [m for m in mismatches if m["tenant_id"] == str(self.eu_tenant.id)]
        assert len(ours) == 0
