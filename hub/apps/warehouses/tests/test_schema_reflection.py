"""
Tests for ``hub.apps.warehouses.schema_reflection`` — reflect_and_populate.

Tests cover the pre-connector validation paths (missing connection,
missing table name) which are pure logic with no external dependencies.
"""

from unittest import mock

import pytest
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.warehouses.models import WarehouseConnection


@pytest.mark.django_db(transaction=True)
class ReflectAndPopulateTests(TestCase):
    """Tests for reflect_and_populate() validation paths."""

    def setUp(self):
        self.tenant = Tenant.objects.create(name="schema-test-tenant", slug="schema-test-tenant")

    def test_no_connection_raises_value_error(self):
        """Asset with warehouse_connection=None raises ValueError."""
        from hub.apps.warehouses.schema_reflection import reflect_and_populate

        asset = mock.MagicMock()
        asset.warehouse_connection = None
        asset.id = "test-id"

        with self.assertRaises(ValueError):
            reflect_and_populate(asset)
        assert "no warehouse_connection" in str(ctx.exception).lower()

    def test_no_table_name_in_metadata_raises_value_error(self):
        """Asset with no table_name in metadata and no override raises ValueError."""
        from hub.apps.warehouses.schema_reflection import reflect_and_populate

        conn = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="test-conn",
            warehouse_type="SNOWFLAKE",
            config={"account": "test"},
        )
        asset = mock.MagicMock()
        asset.warehouse_connection = conn
        asset.id = "test-id"
        asset.metadata = {}  # No table_name or external_table_ref

        with self.assertRaises(ValueError):
            reflect_and_populate(asset)
        assert "cannot determine table name" in str(ctx.exception).lower()

    def test_override_table_name_bypasses_metadata(self):
        """When table_name is explicitly provided, metadata is not consulted.
        The function must NOT raise ValueError (the error it raises when
        metadata is missing).  Connection-layer errors are expected — no
        real warehouse is available."""
        from hub.apps.warehouses.exceptions import WarehouseConnectionError
        from hub.apps.warehouses.schema_reflection import reflect_and_populate

        conn = WarehouseConnection.objects.create(
            tenant=self.tenant,
            name="test-conn",
            warehouse_type="SNOWFLAKE",
            config={"account": "test"},
        )
        asset = mock.MagicMock()
        asset.warehouse_connection = conn
        asset.id = "test-id"
        asset.metadata = {}  # No table_name, but override provided

        try:
            reflect_and_populate(asset, table_name="users")
        except ValueError:
            self.fail(
                "reflect_and_populate raised ValueError for a valid table_name "
                "override — the override should bypass the metadata check"
            )
        except WarehouseConnectionError:
            pass  # Expected — no real warehouse
        except Exception:
            # Other connector-layer errors (e.g. ImportError, OSError) also
            # mean we got past the name check — but we must verify it is not
            # a ValueError masquerading as something else.  Any non-ValueError
            # from the connector layer is acceptable.
            pass
