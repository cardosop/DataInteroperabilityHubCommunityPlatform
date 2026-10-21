"""
Tests for ``hub.apps.warehouses.schema_drift`` — schema drift detection.

Tests the real ``check_schema_drift()`` function which compares the
Hub-side Dataset.schema_json against the live warehouse schema.
"""

from unittest import mock

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.warehouses.models import WarehouseConnection


@pytest.mark.django_db(transaction=True)
class CheckSchemaDriftTests(TestCase):
    """Tests for check_schema_drift()."""

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="drift-test-tenant",
            slug="drift-test-tenant",
            warehouse_connectivity_enabled=True,
        )
        self.connection = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="drift-conn",
            warehouse_type="snowflake",
            config={"account": "test"},
        )

    def test_no_drift_when_no_dataset(self):
        """Returns None when asset has no datasets."""
        from hub.apps.warehouses.schema_drift import check_schema_drift

        asset = mock.MagicMock()
        asset.datasets.first.return_value = None

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is None

    def test_no_drift_when_no_schema_json(self):
        """Returns None when dataset has no schema_json."""
        from hub.apps.warehouses.schema_drift import check_schema_drift

        dataset = mock.MagicMock()
        dataset.schema_json = None
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is None

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_no_drift_when_schemas_identical(self, mock_get_connector):
        """Returns None when hub and warehouse schemas match."""
        from collections import namedtuple

        from hub.apps.warehouses.schema_drift import check_schema_drift

        Col = namedtuple("Col", ["name", "data_type"])
        mock_connector = mock.MagicMock()
        mock_connector.reflect_schema.return_value = [
            Col("id", "INTEGER"),
            Col("name", "VARCHAR"),
        ]
        mock_get_connector.return_value = mock_connector

        dataset = mock.MagicMock()
        dataset.name = "users"
        # List format: each entry has name + data_type
        dataset.schema_json = [
            {"name": "id", "data_type": "INTEGER"},
            {"name": "name", "data_type": "VARCHAR"},
        ]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-id"
        asset.name = "users"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is None

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_drift_detected_added_column(self, mock_get_connector):
        """Detects when warehouse has columns not in hub schema."""
        from collections import namedtuple

        from hub.apps.warehouses.schema_drift import check_schema_drift

        Col = namedtuple("Col", ["name", "data_type"])
        mock_connector = mock.MagicMock()
        mock_connector.reflect_schema.return_value = [
            Col("id", "INTEGER"),
            Col("name", "VARCHAR"),
            Col("email", "VARCHAR"),  # new column
        ]
        mock_get_connector.return_value = mock_connector

        dataset = mock.MagicMock()
        dataset.name = "users"
        dataset.schema_json = [
            {"name": "id", "data_type": "INTEGER"},
            {"name": "name", "data_type": "VARCHAR"},
        ]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-id"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is not None
        assert "email" in result["added_columns"]

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_drift_detected_removed_column(self, mock_get_connector):
        """Detects when hub schema has columns not in warehouse."""
        from collections import namedtuple

        from hub.apps.warehouses.schema_drift import check_schema_drift

        Col = namedtuple("Col", ["name", "data_type"])
        mock_connector = mock.MagicMock()
        mock_connector.reflect_schema.return_value = [
            Col("id", "INTEGER"),
        ]
        mock_get_connector.return_value = mock_connector

        dataset = mock.MagicMock()
        dataset.name = "users"
        dataset.schema_json = [
            {"name": "id", "data_type": "INTEGER"},
            {"name": "old_col", "data_type": "VARCHAR"},
        ]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-id"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is not None
        assert "old_col" in result["removed_columns"]

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_drift_detected_type_change(self, mock_get_connector):
        """Detects when a column's data type has changed."""
        from collections import namedtuple

        from hub.apps.warehouses.schema_drift import check_schema_drift

        Col = namedtuple("Col", ["name", "data_type"])
        mock_connector = mock.MagicMock()
        mock_connector.reflect_schema.return_value = [
            Col("id", "BIGINT"),  # changed from INTEGER
        ]
        mock_get_connector.return_value = mock_connector

        dataset = mock.MagicMock()
        dataset.name = "users"
        dataset.schema_json = [
            {"name": "id", "data_type": "INTEGER"},
        ]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-id"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is not None
        assert "id" in result["type_changes"]

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_connector_error_returns_none(self, mock_get_connector):
        """If connector fails, returns None gracefully."""
        from hub.apps.warehouses.schema_drift import check_schema_drift

        mock_get_connector.side_effect = RuntimeError("connection failed")

        dataset = mock.MagicMock()
        dataset.name = "users"
        dataset.schema_json = [{"name": "id", "data_type": "INTEGER"}]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-id"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is None

    @mock.patch("hub.apps.warehouses.schema_drift._get_connector")
    def test_drift_report_contains_expected_keys(self, mock_get_connector):
        """Drift report dict has all expected fields."""
        from collections import namedtuple

        from hub.apps.warehouses.schema_drift import check_schema_drift

        Col = namedtuple("Col", ["name", "data_type"])
        mock_connector = mock.MagicMock()
        mock_connector.reflect_schema.return_value = [
            Col("id", "INTEGER"),
            Col("extra", "TEXT"),
        ]
        mock_get_connector.return_value = mock_connector

        dataset = mock.MagicMock()
        dataset.name = "users"
        dataset.schema_json = [{"name": "id", "data_type": "INTEGER"}]
        asset = mock.MagicMock()
        asset.datasets.first.return_value = dataset
        asset.id = "test-uuid"

        result = check_schema_drift(
            asset=asset,
            warehouse_connection=self.connection,
            tenant=self.tenant,
        )
        assert result is not None
        assert "warehouse_type" in result
        assert "asset_id" in result
        assert "added_columns" in result
        assert "removed_columns" in result
        assert "type_changes" in result
        assert result["warehouse_type"] == "snowflake"
