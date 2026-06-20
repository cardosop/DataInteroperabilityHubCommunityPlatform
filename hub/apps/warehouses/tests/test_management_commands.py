"""
Unit tests for warehouse management commands.

Tests check_warehouse_schema_drift command.
"""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import TestCase

from hub.apps.assets.models import Asset, DataStrategy
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class CheckWarehouseSchemaDriftTest(TestCase):
    """Test check_warehouse_schema_drift command"""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="DriftTest",
            slug="drift-test",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.out = StringIO()
        self.err = StringIO()

    @patch("hub.apps.warehouses.schema_drift.check_schema_drift")
    @patch("hub.apps.audit.utils.create_audit_event")
    def test_dry_run_reports_drift_no_modification(self, mock_audit, mock_check):
        """Dry run detects drift but does NOT update Dataset flags"""
        from hub.apps.warehouses.models import WarehouseConnection

        wh = WarehouseConnection.objects.create(
            name="test-wh",
            tenant=self.tenant,
            warehouse_type="SNOWFLAKE",
            config={"account": "test", "database": "testdb"},
            is_active=True,
        )
        Asset.objects.create(
            name="drift_asset",
            key="drift_asset_key",
            tenant=self.tenant,
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=wh,
        )
        mock_check.return_value = {
            "added_columns": [{"name": "new_col", "type": "VARCHAR"}],
            "removed_columns": [],
            "type_changes": [],
        }

        call_command("check_warehouse_schema_drift", "--dry-run", stdout=self.out, stderr=self.err)

        output = self.out.getvalue()
        self.assertIn("DRIFT", output)
        self.assertIn("added=1", output)
        self.assertIn("DRY RUN", output)
        # Audit event is still emitted even in dry run
        self.assertTrue(mock_audit.called)

    @patch("hub.apps.warehouses.schema_drift.check_schema_drift")
    @patch("hub.apps.audit.utils.create_audit_event")
    def test_no_drift_assets(self, mock_audit, mock_check):
        """Command reports zero drift when schemas match"""
        from hub.apps.warehouses.models import WarehouseConnection

        wh = WarehouseConnection.objects.create(
            name="clean-wh",
            tenant=self.tenant,
            warehouse_type="SNOWFLAKE",
            config={"account": "test", "database": "testdb"},
            is_active=True,
        )
        Asset.objects.create(
            name="clean_asset",
            key="clean_asset_key",
            tenant=self.tenant,
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=wh,
        )
        mock_check.return_value = None  # No drift

        call_command("check_warehouse_schema_drift", stdout=self.out, stderr=self.err)

        output = self.out.getvalue()
        self.assertIn("0 of", output)
        self.assertNotIn("DRIFT", output)

    @patch("hub.apps.warehouses.schema_drift.check_schema_drift")
    def test_single_asset_filter(self, mock_check):
        """--asset-id limits check to specified asset"""
        from hub.apps.warehouses.models import WarehouseConnection

        wh = WarehouseConnection.objects.create(
            name="wh",
            tenant=self.tenant,
            warehouse_type="SNOWFLAKE",
            config={"account": "test", "database": "testdb"},
            is_active=True,
        )
        asset1 = Asset.objects.create(
            name="asset1",
            key="asset1_key",
            tenant=self.tenant,
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=wh,
        )
        Asset.objects.create(
            name="asset2",
            key="asset2_key",
            tenant=self.tenant,
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=wh,
        )
        mock_check.return_value = None

        call_command(
            "check_warehouse_schema_drift",
            "--asset-id",
            str(asset1.id),
            stdout=self.out,
            stderr=self.err,
        )

        output = self.out.getvalue()
        self.assertIn("Checking 1", output)

    @patch("hub.apps.warehouses.schema_drift.check_schema_drift")
    def test_tenant_filter(self, mock_check):
        """--tenant-id limits check to specified tenant"""
        from hub.apps.warehouses.models import WarehouseConnection

        wh = WarehouseConnection.objects.create(
            name="wh",
            tenant=self.tenant,
            warehouse_type="SNOWFLAKE",
            config={"account": "test", "database": "testdb"},
            is_active=True,
        )
        Asset.objects.create(
            name="asset",
            key="asset_key",
            tenant=self.tenant,
            data_strategy=DataStrategy.LIVE_QUERY,
            warehouse_connection=wh,
        )
        mock_check.return_value = None

        call_command(
            "check_warehouse_schema_drift",
            "--tenant-id",
            str(self.tenant.id),
            stdout=self.out,
            stderr=self.err,
        )

        self.assertTrue(mock_check.called)
