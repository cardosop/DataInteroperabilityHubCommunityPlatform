"""
Comprehensive Integration Tests for CKAN Connector Push Operations

**DEPRECATED**: CKAN connector is harvest-only (PULL only).
All push operations (create_listing, update_listing, publish_resource, sync_push, map_from_hub_asset)
now raise NotImplementedError.

This test file validates that push operations correctly raise NotImplementedError.
CKAN instances are public data portals that should be harvested FROM, not pushed TO.
"""
import pytest
from django.test import TestCase

from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.base import (
    MarketplaceType,
    MarketplaceListing,
    MarketplaceResource,
)
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    marketplace_available,
    # Backward compatibility (deprecated)
    ckan_available,
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
        if not ckan_available():
            pytest.skip("No CKAN instance available for testing")

        # Create connector using centralized utility
        cls.connector = create_test_connector(verify_connection=True)

        if not cls.connector:
            pytest.skip("Cannot create or connect to CKAN instance for testing")

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
                'id': asset_id,
                'name': 'Test Asset',
                'description': 'Test description',
            }

        with self.assertRaises(NotImplementedError) as context:
            self.connector.sync_push(
                asset_ids=["test-asset-1"],
                options={'asset_data_provider': asset_data_provider}
            )

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test that map_from_hub_asset raises NotImplementedError."""
        asset_data = {
            'id': 'test-asset',
            'name': 'Test Asset',
            'description': 'Test description',
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
