"""
Comprehensive Integration Tests for CKAN Connector Push Operations

**DEPRECATED**: CKAN connector is harvest-only (PULL only).
All push operations (create_listing, update_listing, publish_resource, sync_push, map_from_hub_asset)
now raise NotImplementedError.

This test file validates that push operations correctly raise NotImplementedError.
CKAN instances are public data portals that should be harvested FROM, not pushed TO.
"""

import unittest
import pytest
from django.test import TestCase

from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
)
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    marketplace_available,
)


@pytest.mark.integration
class TestCKANConnectorPushOperations(TestCase):
    """
    Tests that CKAN connector push operations correctly raise NotImplementedError.

    CKAN connector is harvest-only (PULL only) as CKAN instances are public
    data portals that should be harvested FROM, not pushed TO.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real CKAN instance."""
        super().setUpClass()

        # Use centralized test utilities
        if not marketplace_available():
            raise unittest.SkipTest("No CKAN instance available for testing")

        # Create connector using centralized utility
        cls.connector = create_test_connector(verify_connection=True)

        if not cls.connector:
            raise unittest.SkipTest("Cannot create or connect to CKAN instance for testing")

    def setUp(self):
        """Set up test fixtures."""
        if not self.connector:
            self.skipTest("No CKAN connector available")

    def test_create_listing_raises_not_implemented(self):
        """Test that create_listing raises NotImplementedError."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test description",
        )

        with self.assertRaises(NotImplementedError) as context:
            self.connector.create_listing(listing)

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_update_listing_raises_not_implemented(self):
        """Test that update_listing raises NotImplementedError."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Updated Test Package",
            description="Updated description",
        )

        with self.assertRaises(NotImplementedError) as context:
            self.connector.update_listing("test-package", listing)

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_publish_resource_raises_not_implemented(self):
        """Test that publish_resource raises NotImplementedError."""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
            description="Test resource description",
            url="https://example.com/resource.csv",
            format="CSV",
        )

        with self.assertRaises(NotImplementedError) as context:
            self.connector.publish_resource("test-package", resource)

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_sync_push_raises_not_implemented(self):
        """Test that sync_push raises NotImplementedError."""

        def asset_data_provider(asset_id: str):
            return {
                "id": asset_id,
                "name": "Test Asset",
                "description": "Test description",
            }

        with self.assertRaises(NotImplementedError) as context:
            self.connector.sync_push(
                asset_ids=["test-asset-1"], options={"asset_data_provider": asset_data_provider}
            )

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test that map_from_hub_asset raises NotImplementedError."""
        asset_data = {
            "id": "test-asset",
            "name": "Test Asset",
            "description": "Test description",
        }

        with self.assertRaises(NotImplementedError) as context:
            self.connector.map_from_hub_asset(asset_data)

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_supported_sync_directions_is_pull_only(self):
        """Test that supported_sync_directions only includes PULL."""
        from hub.apps.integrations.base import SyncDirection

        supported = self.connector.supported_sync_directions
        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0], SyncDirection.PULL)
        self.assertNotIn(SyncDirection.PUSH, supported)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, supported)

    def test_create_listing_with_none(self):
        """Test create_listing() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.create_listing(None)  # type: ignore[arg-type]

    def test_update_listing_with_empty_id(self):
        """Test update_listing() error handling with empty ID"""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )
        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.update_listing("", listing)

    def test_update_listing_with_none_id(self):
        """Test update_listing() error handling with None ID"""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.update_listing(None, listing)  # type: ignore[arg-type]

    def test_publish_resource_with_empty_package_id(self):
        """Test publish_resource() error handling with empty package ID"""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
        )
        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.publish_resource("", resource)

    def test_publish_resource_with_none_package_id(self):
        """Test publish_resource() error handling with None package ID"""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
        )
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.publish_resource(None, resource)  # type: ignore[arg-type]

    def test_sync_push_with_empty_asset_ids(self):
        """Test sync_push() error handling with empty asset_ids list"""

        def asset_data_provider(asset_id: str):
            return {"id": asset_id, "name": "Test"}

        with self.assertRaises((NotImplementedError, ValueError)):
            self.connector.sync_push(
                asset_ids=[], options={"asset_data_provider": asset_data_provider}
            )

    def test_map_from_hub_asset_with_none(self):
        """Test map_from_hub_asset() error handling with None"""
        with self.assertRaises((NotImplementedError, ValueError, TypeError)):
            self.connector.map_from_hub_asset(None)  # type: ignore[arg-type]

    def test_map_from_hub_asset_with_empty_dict(self):
        """Test map_from_hub_asset() error handling with empty dict"""
        with self.assertRaises(NotImplementedError):
            self.connector.map_from_hub_asset({})
