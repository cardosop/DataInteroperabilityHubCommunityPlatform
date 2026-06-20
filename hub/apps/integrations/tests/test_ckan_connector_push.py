"""
Unit Tests for CKAN Connector Push Operations (Harvest-Only Contract)

CKAN connector is harvest-only (PULL only). All push operations
(create_listing, update_listing, publish_resource, sync_push, map_from_hub_asset)
must raise NotImplementedError unconditionally — no parameter validation, no
network calls, no side effects.

These are pure unit tests: they instantiate CKANConnector directly with a
dummy base_url (no connectivity required) and verify the harvest-only contract.
"""

import unittest

from django.test import SimpleTestCase

from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
)
from hub.apps.integrations.connectors.ckan_connector import CKANConnector


class TestCKANConnectorPushOperations(SimpleTestCase):
    """
    Unit tests verifying that CKAN connector push operations raise
    NotImplementedError (harvest-only contract).

    No external connectivity, mocks, or stubs required — the connector
    raises NotImplementedError unconditionally before any network I/O.
    """

    @classmethod
    def setUpClass(cls):
        """Create a CKANConnector with a dummy base_url (no network calls)."""
        super().setUpClass()
        cls.connector = CKANConnector(base_url="https://demo.ckan.org")

    # ── create_listing ──────────────────────────────────────────────────

    def test_create_listing_raises_not_implemented(self):
        """create_listing() raises NotImplementedError unconditionally."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
            description="Test description",
        )

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.create_listing(listing)

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_create_listing_with_none(self):
        """create_listing(None) raises NotImplementedError (no validation first)."""
        with self.assertRaises(NotImplementedError):
            self.connector.create_listing(None)  # type: ignore[arg-type]

    # ── update_listing ──────────────────────────────────────────────────

    def test_update_listing_raises_not_implemented(self):
        """update_listing() raises NotImplementedError unconditionally."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Updated Test Package",
            description="Updated description",
        )

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.update_listing("test-package", listing)

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_update_listing_with_empty_id(self):
        """update_listing('', ...) raises NotImplementedError (no validation first)."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )
        with self.assertRaises(NotImplementedError):
            self.connector.update_listing("", listing)

    def test_update_listing_with_none_id(self):
        """update_listing(None, ...) raises NotImplementedError (no validation first)."""
        listing = MarketplaceListing(
            marketplace_id="test-package",
            marketplace_type=MarketplaceType.CKAN_INSTANCE,
            title="Test Package",
        )
        with self.assertRaises(NotImplementedError):
            self.connector.update_listing(None, listing)  # type: ignore[arg-type]

    # ── publish_resource ────────────────────────────────────────────────

    def test_publish_resource_raises_not_implemented(self):
        """publish_resource() raises NotImplementedError unconditionally."""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
            description="Test resource description",
            url="https://example.com/resource.csv",
            format="CSV",
        )

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.publish_resource("test-package", resource)

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_publish_resource_with_empty_package_id(self):
        """publish_resource('', ...) raises NotImplementedError (no validation first)."""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
        )
        with self.assertRaises(NotImplementedError):
            self.connector.publish_resource("", resource)

    def test_publish_resource_with_none_package_id(self):
        """publish_resource(None, ...) raises NotImplementedError (no validation first)."""
        resource = MarketplaceResource(
            resource_id="test-resource",
            resource_type="FILE",
            name="Test Resource",
        )
        with self.assertRaises(NotImplementedError):
            self.connector.publish_resource(None, resource)  # type: ignore[arg-type]

    # ── sync_push ───────────────────────────────────────────────────────

    def test_sync_push_raises_not_implemented(self):
        """sync_push() raises NotImplementedError unconditionally."""

        def asset_data_provider(asset_id: str):
            return {
                "id": asset_id,
                "name": "Test Asset",
                "description": "Test description",
            }

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.sync_push(
                asset_ids=["test-asset-1"],
                options={"asset_data_provider": asset_data_provider},
            )

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_sync_push_with_empty_asset_ids(self):
        """sync_push(asset_ids=[]) raises NotImplementedError (no validation first)."""

        def asset_data_provider(asset_id: str):
            return {"id": asset_id, "name": "Test"}

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(
                asset_ids=[], options={"asset_data_provider": asset_data_provider}
            )

    # ── map_from_hub_asset ──────────────────────────────────────────────

    def test_map_from_hub_asset_raises_not_implemented(self):
        """map_from_hub_asset() raises NotImplementedError unconditionally."""
        asset_data = {
            "id": "test-asset",
            "name": "Test Asset",
            "description": "Test description",
        }

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.map_from_hub_asset(asset_data)

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_map_from_hub_asset_with_none(self):
        """map_from_hub_asset(None) raises NotImplementedError (no validation first)."""
        with self.assertRaises(NotImplementedError):
            self.connector.map_from_hub_asset(None)  # type: ignore[arg-type]

    def test_map_from_hub_asset_with_empty_dict(self):
        """map_from_hub_asset({}) raises NotImplementedError (no validation first)."""
        with self.assertRaises(NotImplementedError):
            self.connector.map_from_hub_asset({})

    # ── supported_sync_directions ───────────────────────────────────────

    def test_supported_sync_directions_is_pull_only(self):
        """supported_sync_directions only includes PULL."""
        supported = self.connector.supported_sync_directions
        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0], SyncDirection.PULL)
        self.assertNotIn(SyncDirection.PUSH, supported)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, supported)
