"""
Comprehensive Integration Tests for CKAN Connector Sync Operations

Tests sync operations (sync_pull) using real CKAN instances.

**Note**: sync_push operations raise NotImplementedError as CKAN connector is harvest-only (PULL only).
Unit tests for sync_push NotImplementedError behaviour run without external connectivity
(see ``TestCKANConnectorSyncPushUnit``); integration tests for sync_pull require a live CKAN
instance and live in ``TestCKANConnectorSyncOperations``.

No mocks or stubs - all integration tests use actual CKAN API endpoints.

Uses centralized test utilities for consistent configuration.
"""

import unittest
import uuid
from typing import Any
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.core.services.base import ConnectionError as HubConnectionError
from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    get_test_api_key,  # Backward compatibility
    marketplace_available,
)


def has_write_permissions() -> bool:
    """Check if we have write permissions (API key available)."""
    api_key = get_test_api_key()
    if not api_key:
        return False

    # Try to verify API key works using centralized utilities
    connector = create_test_connector(api_key=api_key, verify_connection=False)
    if not connector:
        return False

    try:
        result = connector.authenticate({"api_key": api_key})
        return result
    except (HubConnectionError, ValueError):
        return False


@pytest.mark.integration
class TestCKANConnectorSyncOperations(TestCase):
    """
    Comprehensive integration tests for CKAN connector sync operations.

    Tests use real CKAN instances - no mocks or stubs.
    Write operations require API key - tests will skip if not available.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real CKAN instance."""
        # Check skip conditions BEFORE super().setUpClass() so that if we
        # raise SkipTest, no class-level atomics are opened and the PG
        # connection is not left in a stale transaction for the next class.
        if not marketplace_available():
            raise unittest.SkipTest("No CKAN instance available for testing")

        super().setUpClass()

        try:
            # Create connector using centralized utility
            cls.connector = create_test_connector(verify_connection=True)

            if not cls.connector:
                raise unittest.SkipTest("Cannot create or connect to CKAN instance for testing")

            # Cache connector URL and API key for backward compatibility
            cls.ckan_url = cls.connector.base_url
            cls.ckan_api_key = cls.connector.api_key

            # Track created packages for cleanup
            cls.created_package_ids = []
        except Exception:
            cls._rollback_atomics(cls.cls_atomics)
            raise

    def setUp(self):
        """Set up test fixtures."""
        if not self.ckan_url:
            self.skipTest("No CKAN instance available")

    def tearDown(self):
        """Clean up test data."""
        # Cleanup is handled by individual tests or skipped if no write permissions

    def test_sync_pull_basic(self):
        """Test basic sync_pull operation."""
        result = self.connector.sync_pull(options={"limit": 5})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertGreaterEqual(result.total_items, 0)
        self.assertGreaterEqual(result.successful_items, 0)

        if result.metadata.get("reason") == "no_listings_found":
            self.skipTest("CKAN test instance has no listings — external state, not a regression")
        self.assertIn("mappings", result.metadata)
        self.assertIsInstance(result.metadata["mappings"], list)

    def test_sync_pull_with_listing_ids(self):
        """Test sync_pull with specific listing IDs."""
        # Get a few listings first
        listings = self.connector.list_listings(limit=3)
        if not listings:
            self.skipTest("No listings available for testing")

        listing_ids = [listing.marketplace_id for listing in listings[:2]]
        result = self.connector.sync_pull(listing_ids=listing_ids)

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, len(listing_ids))
        self.assertGreaterEqual(result.successful_items, 0)
        self.assertIn("mappings", result.metadata)
        self.assertEqual(len(result.metadata["mappings"]), result.successful_items)

    def test_sync_pull_with_filters(self):
        """Test sync_pull with filters."""
        result = self.connector.sync_pull(filters={"limit": 3}, options={"limit": 3})

        self.assertIsInstance(result, SyncResult)
        self.assertLessEqual(result.total_items, 3)
        if result.metadata.get("reason") == "no_listings_found":
            self.skipTest("CKAN test instance has no listings — external state, not a regression")
        self.assertIn("mappings", result.metadata)

    def test_sync_pull_dry_run(self):
        """Test sync_pull in dry-run mode."""
        result = self.connector.sync_pull(options={"dry_run": True, "limit": 5})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertTrue(result.metadata.get("dry_run"))

        if result.metadata.get("reason") == "no_listings_found":
            self.skipTest("CKAN test instance has no listings — external state, not a regression")
        # In dry-run, mappings should still be created for validation
        self.assertIn("mappings", result.metadata)

    def test_sync_pull_without_resources(self):
        """Test sync_pull without fetching resources."""
        result = self.connector.sync_pull(options={"include_resources": False, "limit": 3})

        self.assertIsInstance(result, SyncResult)
        self.assertFalse(result.metadata.get("include_resources"))
        if result.metadata.get("reason") == "no_listings_found":
            self.skipTest("CKAN test instance has no listings — external state, not a regression")
        # Mappings should still be created
        self.assertIn("mappings", result.metadata)

    def test_sync_pull_nonexistent_listing(self):
        """Test sync_pull with non-existent listing IDs.

        Source catches NotFoundError per listing, counts as skipped, returns
        COMPLETED with total_items=len(listing_ids) (sync_pull lines 1455-1465).
        """
        fake_id = f"nonexistent-{uuid.uuid4().hex[:8]}"
        result = self.connector.sync_pull(listing_ids=[fake_id])

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, 1)
        self.assertEqual(result.successful_items, 0)
        self.assertEqual(result.skipped_items, 1)
        self.assertGreater(len(result.errors), 0)
        self.assertTrue(
            any(fake_id in err for err in result.errors),
            f"Errors should mention {fake_id}: {result.errors}"
        )

    def test_sync_pull_empty_result(self):
        """Test sync_pull with filters that return no results."""
        # Use a filter that's unlikely to match anything
        result = self.connector.sync_pull(
            filters={"q": f"nonexistent-search-term-{uuid.uuid4().hex[:8]}"}, options={"limit": 10}
        )

        self.assertIsInstance(result, SyncResult)
        # Should complete successfully (may have 0 items or items that fail mapping)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])
        # Total items may be 0 or greater if CKAN returns results but mapping fails
        self.assertGreaterEqual(result.total_items, 0)

    def test_sync_pull_mapping_structure(self):
        """Test that sync_pull returns properly structured mappings."""
        result = self.connector.sync_pull(options={"limit": 1})

        if result.total_items == 0:
            self.skipTest("No listings available for mapping test")

        self.assertIn("mappings", result.metadata)
        mappings = result.metadata["mappings"]

        if mappings:
            mapping = mappings[0]
            self.assertIn("listing_id", mapping)
            self.assertIn("mapping", mapping)
            # Verify mapping structure
            asset_mapping = mapping["mapping"]
            self.assertIsNotNone(asset_mapping.asset_data)
            self.assertEqual(asset_mapping.source_type, "FEDERATED")

    # sync_push NotImplementedError contract is verified in
    # ``TestCKANConnectorSyncPushUnit`` (unit tests — no live CKAN needed)

    def test_sync_operations_connection_error(self):
        """Test that sync operations handle connection errors gracefully."""
        invalid_connector = CKANConnector(base_url="https://invalid-ckan-instance-xyz-12345.com")

        # Test sync_pull - should return FAILED status, not raise exception
        result = invalid_connector.sync_pull(options={"limit": 1})
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.FAILED)
        self.assertGreater(len(result.errors), 0)

        # Test sync_push - should raise NotImplementedError (harvest-only)
        def asset_data_provider(asset_id: str) -> dict[str, Any]:
            return {"id": asset_id, "name": "Test"}

        with self.assertRaises(NotImplementedError):
            invalid_connector.sync_push(
                asset_ids=["test"], options={"asset_data_provider": asset_data_provider}
            )

    def test_sync_pull_with_zero_limit(self):
        """Test sync_pull() edge case with zero limit"""
        result = self.connector.sync_pull(options={"limit": 0})
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.successful_items, 0)

    def test_sync_pull_with_very_large_limit(self):
        """Test sync_pull() edge case with very large limit"""
        result = self.connector.sync_pull(options={"limit": 1000000})
        self.assertIsInstance(result, SyncResult)
        # Should handle large limit gracefully
        self.assertLessEqual(result.total_items, 1000000)

    def test_sync_pull_with_none_options(self):
        """Test sync_pull() handles None options gracefully"""
        result = self.connector.sync_pull(options=None)
        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED])

    def test_sync_pull_with_empty_options(self):
        """Test sync_pull() handles empty options dictionary"""
        result = self.connector.sync_pull(options={})
        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED])

    def test_sync_pull_with_invalid_filters(self):
        """Test sync_pull with unknown filter keys.

        Unknown filter keys are silently ignored by _list_listings_via_search
        (only q, fq, and organization are extracted).  The call should return
        a SyncResult without crashing.
        """
        result = self.connector.sync_pull(filters={"invalid": "filter"})
        self.assertIsInstance(result, SyncResult)
        self.assertIn(
            result.status,
            [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED],
        )

    def test_sync_pull_with_none_filters(self):
        """Test sync_pull() handles None filters gracefully"""
        result = self.connector.sync_pull(filters=None)
        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED])

    def test_sync_pull_with_empty_listing_ids(self):
        """Test sync_pull() edge case with empty listing_ids list"""
        result = self.connector.sync_pull(listing_ids=[])
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.successful_items, 0)

    def test_sync_pull_with_invalid_listing_ids(self):
        """Test sync_pull with listing IDs that don't exist.

        Each non-existent listing is caught as NotFoundError and counted as
        skipped (source lines 1455-1465).  Total items = len(listing_ids).
        """
        result = self.connector.sync_pull(listing_ids=["invalid-id-1", "invalid-id-2"])
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, 2)
        self.assertEqual(result.successful_items, 0)
        self.assertEqual(result.skipped_items, 2)
        self.assertGreater(len(result.errors), 0)


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: sync_push NotImplementedError contract (no live CKAN needed)
# ══════════════════════════════════════════════════════════════════════════════


class TestCKANConnectorSyncPushUnit(SimpleTestCase):
    """
    Unit tests verifying that sync_push unconditionally raises NotImplementedError.

    CKAN connector is harvest-only — sync_push must reject any call before
    parameter validation, network I/O, or side effects.  These tests instantiate
    CKANConnector directly with a dummy base_url; no external connectivity,
    mocks, or stubs required.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connector = CKANConnector(base_url="https://demo.ckan.org")

    # ── helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _asset_data_provider(asset_id: str) -> dict[str, Any]:
        return {
            "id": asset_id,
            "name": f"Test Asset {asset_id}",
            "description": "Test asset for sync_push",
            "key": f"test-{asset_id[:8]}",
        }

    @staticmethod
    def _odps_metadata_provider(asset_id: str) -> dict[str, Any]:
        return {"product_name": "Test Product", "version": "1.0.0"}

    # ── basic sync_push ──────────────────────────────────────────────────

    def test_sync_push_raises_not_implemented(self):
        """sync_push() with valid args raises NotImplementedError."""
        asset_ids = ["test-asset-1", "test-asset-2"]

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={"asset_data_provider": self._asset_data_provider, "dry_run": True},
            )

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_sync_push_with_metadata_raises_not_implemented(self):
        """sync_push() with odps_metadata_provider raises NotImplementedError."""
        asset_ids = ["test-asset-1"]

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={
                    "asset_data_provider": self._asset_data_provider,
                    "odps_metadata_provider": self._odps_metadata_provider,
                    "dry_run": True,
                },
            )

    def test_sync_push_empty_asset_ids_raises_not_implemented(self):
        """sync_push(asset_ids=[]) raises NotImplementedError (no validation first)."""
        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(asset_ids=[])

    def test_sync_push_missing_provider_raises_not_implemented(self):
        """sync_push() without asset_data_provider raises NotImplementedError."""
        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(asset_ids=["test-asset-1"], options={})

    def test_sync_push_force_update_raises_not_implemented(self):
        """sync_push() with force_update=True raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.sync_push(
                asset_ids=["test-asset-1"],
                options={
                    "asset_data_provider": self._asset_data_provider,
                    "force_update": True,
                    "dry_run": True,
                },
            )

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_sync_push_error_handling_raises_not_implemented(self):
        """sync_push() with empty asset data provider raises NotImplementedError."""

        def empty_provider(asset_id: str) -> dict[str, Any]:
            return {}

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(
                asset_ids=["test-asset-1"],
                options={"asset_data_provider": empty_provider, "dry_run": True},
            )

    def test_sync_push_partial_success_raises_not_implemented(self):
        """sync_push() with multiple asset IDs raises NotImplementedError."""
        asset_ids = ["asset-1", "asset-2"]

        with self.assertRaises(NotImplementedError) as ctx:
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={"asset_data_provider": self._asset_data_provider, "dry_run": True},
            )

        message = str(ctx.exception).lower()
        self.assertIn("harvest-only", message)
        self.assertIn("pull only", message)

    def test_sync_operations_connection_error_push(self):
        """sync_push() on a connector with an unreachable base_url still raises NotImplementedError."""
        invalid_connector = CKANConnector(
            base_url="https://invalid-ckan-instance-xyz-12345.com"
        )

        with self.assertRaises(NotImplementedError):
            invalid_connector.sync_push(
                asset_ids=["test"], options={"asset_data_provider": self._asset_data_provider}
            )


# ══════════════════════════════════════════════════════════════════════════════
# Unit tests: sync_pull status transitions (mocked — no live CKAN needed)
# ══════════════════════════════════════════════════════════════════════════════


class TestCKANConnectorSyncPullStatusUnit(SimpleTestCase):
    """Unit tests for sync_pull status transitions using mocks.

    These verify that sync_pull returns the correct SyncStatus for
    various success/failure combinations without needing a live CKAN.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.connector = CKANConnector(base_url="https://demo.ckan.org")

    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.get_listing")
    @patch("hub.apps.integrations.connectors.ckan_connector.CKANConnector.map_to_hub_asset")
    def test_sync_pull_returns_partial_on_mixed_results(self, mock_map, mock_get):
        """sync_pull returns PARTIAL when some listings succeed and some fail."""
        from hub.apps.assets.models import AssetSourceType

        mock_get.side_effect = [
            MarketplaceListing(
                marketplace_id="package-1",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 1",
            ),
            MarketplaceListing(
                marketplace_id="package-2",
                marketplace_type=MarketplaceType.CKAN_INSTANCE,
                title="Package 2",
            ),
        ]

        # First mapping succeeds, second fails
        mock_map.side_effect = [
            MarketplaceAssetMapping(
                asset_data={"name": "Package 1"},
                source_type=AssetSourceType.FEDERATED,
                source_metadata={"listing_id": "package-1"},
            ),
            Exception("Mapping failed"),
        ]

        result = self.connector.sync_pull(
            listing_ids=["package-1", "package-2"],
            options={"dry_run": False},
        )

        self.assertEqual(result.status, SyncStatus.PARTIAL)
        self.assertEqual(result.total_items, 2)
        self.assertEqual(result.successful_items, 1)
        self.assertEqual(result.failed_items, 1)
        self.assertGreater(len(result.errors), 0)
