"""
Comprehensive Integration Tests for CKAN Connector Sync Operations

Tests sync operations (sync_pull) using real CKAN instances.

**Note**: sync_push operations raise NotImplementedError as CKAN connector is harvest-only (PULL only).
No mocks or stubs - all tests use actual CKAN API endpoints.

Uses centralized test utilities for consistent configuration.
"""
import pytest
import uuid
from typing import Dict, Any
from datetime import datetime

from django.test import TestCase

from hub.apps.integrations.connectors.ckan_connector import CKANConnector
from hub.apps.integrations.base import (
    MarketplaceType,
    MarketplaceListing,
    MarketplaceResource,
    SyncStatus,
    SyncResult,
)
from hub.apps.core.services.base import NotFoundError
from hub.apps.integrations.tests.utils.marketplace_test_helpers import (
    create_test_connector,
    marketplace_available,
    get_test_ckan_url,  # Backward compatibility
    get_test_api_key,   # Backward compatibility
    # Backward compatibility (deprecated)
    ckan_available,
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
        result = connector.authenticate({'api_key': api_key})
        return result
    except Exception:
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
        super().setUpClass()

        # Use centralized test utilities
        if not ckan_available():
            pytest.skip("No CKAN instance available for testing")

        # Create connector using centralized utility
        cls.connector = create_test_connector(verify_connection=True)

        if not cls.connector:
            pytest.skip("Cannot create or connect to CKAN instance for testing")

        # Cache connector URL and API key for backward compatibility
        cls.ckan_url = cls.connector.base_url
        cls.ckan_api_key = cls.connector.api_key

        # Track created packages for cleanup
        cls.created_package_ids = []

    def setUp(self):
        """Set up test fixtures."""
        if not self.ckan_url:
            self.skipTest("No CKAN instance available")

    def tearDown(self):
        """Clean up test data."""
        # Cleanup is handled by individual tests or skipped if no write permissions

    def test_sync_pull_basic(self):
        """Test basic sync_pull operation."""
        result = self.connector.sync_pull(options={'limit': 5})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertGreater(result.total_items, 0)
        self.assertGreaterEqual(result.successful_items, 0)
        self.assertIn('mappings', result.metadata)
        self.assertIsInstance(result.metadata['mappings'], list)

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
        self.assertIn('mappings', result.metadata)
        self.assertEqual(len(result.metadata['mappings']), result.successful_items)

    def test_sync_pull_with_filters(self):
        """Test sync_pull with filters."""
        result = self.connector.sync_pull(
            filters={'limit': 3},
            options={'limit': 3}
        )

        self.assertIsInstance(result, SyncResult)
        self.assertLessEqual(result.total_items, 3)
        self.assertIn('mappings', result.metadata)

    def test_sync_pull_dry_run(self):
        """Test sync_pull in dry-run mode."""
        result = self.connector.sync_pull(
            options={'dry_run': True, 'limit': 5}
        )

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertTrue(result.metadata.get('dry_run'))
        # In dry-run, mappings should still be created for validation
        self.assertIn('mappings', result.metadata)

    def test_sync_pull_without_resources(self):
        """Test sync_pull without fetching resources."""
        result = self.connector.sync_pull(
            options={'include_resources': False, 'limit': 3}
        )

        self.assertIsInstance(result, SyncResult)
        self.assertFalse(result.metadata.get('include_resources'))
        # Mappings should still be created
        self.assertIn('mappings', result.metadata)

    def test_sync_pull_nonexistent_listing(self):
        """Test sync_pull with non-existent listing IDs."""
        fake_id = f"nonexistent-{uuid.uuid4().hex[:8]}"
        result = self.connector.sync_pull(listing_ids=[fake_id])

        self.assertIsInstance(result, SyncResult)
        # Should have skipped the non-existent listing or have it in errors
        # The implementation may return 0 listings if all are not found
        if result.total_items == 0:
            # All listings were not found, check errors
            self.assertGreater(len(result.errors), 0)
            self.assertIn(fake_id, str(result.errors))
        else:
            # Should have skipped items
            self.assertGreater(result.skipped_items, 0)

    def test_sync_pull_empty_result(self):
        """Test sync_pull with filters that return no results."""
        # Use a filter that's unlikely to match anything
        result = self.connector.sync_pull(
            filters={'q': f'nonexistent-search-term-{uuid.uuid4().hex[:8]}'},
            options={'limit': 10}
        )

        self.assertIsInstance(result, SyncResult)
        # Should complete successfully (may have 0 items or items that fail mapping)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])
        # Total items may be 0 or greater if CKAN returns results but mapping fails
        self.assertGreaterEqual(result.total_items, 0)

    def test_sync_pull_mapping_structure(self):
        """Test that sync_pull returns properly structured mappings."""
        result = self.connector.sync_pull(options={'limit': 1})

        if result.total_items == 0:
            self.skipTest("No listings available for mapping test")

        self.assertIn('mappings', result.metadata)
        mappings = result.metadata['mappings']

        if mappings:
            mapping = mappings[0]
            self.assertIn('listing_id', mapping)
            self.assertIn('mapping', mapping)
            # Verify mapping structure
            asset_mapping = mapping['mapping']
            self.assertIsNotNone(asset_mapping.asset_data)
            self.assertEqual(asset_mapping.source_type, 'FEDERATED')

    def test_sync_push_raises_not_implemented(self):
        """Test that sync_push raises NotImplementedError (CKAN connector is harvest-only)."""
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {
                'id': asset_id,
                'name': f'Test Asset {asset_id}',
                'description': 'Test asset for sync_push',
                'key': f'test-asset-{uuid.uuid4().hex[:8]}',
            }

        asset_ids = [f'test-asset-{uuid.uuid4().hex[:8]}' for _ in range(2)]

        with self.assertRaises(NotImplementedError) as context:
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={
                    'asset_data_provider': asset_data_provider,
                    'dry_run': True
                }
            )

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_sync_push_with_metadata_raises_not_implemented(self):
        """Test that sync_push with metadata raises NotImplementedError."""
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {
                'id': asset_id,
                'name': f'Test Asset {asset_id}',
                'description': 'Test asset with metadata',
                'key': f'test-asset-{uuid.uuid4().hex[:8]}',
            }

        def odps_metadata_provider(asset_id: str) -> Dict[str, Any]:
            return {
                'product_name': 'Test Product',
                'version': '1.0.0',
            }

        asset_ids = [f'test-asset-{uuid.uuid4().hex[:8]}']

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={
                    'asset_data_provider': asset_data_provider,
                    'odps_metadata_provider': odps_metadata_provider,
                    'dry_run': True
                }
            )

    def test_sync_push_empty_asset_ids_raises_not_implemented(self):
        """Test that sync_push with empty asset_ids raises NotImplementedError (not ValueError)."""
        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(asset_ids=[])

    def test_sync_push_missing_provider_raises_not_implemented(self):
        """Test that sync_push without asset_data_provider raises NotImplementedError (not ValueError)."""
        asset_ids = ['test-asset-1']

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(asset_ids=asset_ids, options={})

    def test_sync_push_force_update_raises_not_implemented(self):
        """Test that sync_push with force_update raises NotImplementedError."""
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {
                'id': asset_id,
                'name': f'Updated Asset {asset_id}',
                'description': 'Updated description',
                'key': 'test-key',
            }

        with self.assertRaises(NotImplementedError) as context:
            self.connector.sync_push(
                asset_ids=['test-asset-1'],
                options={
                    'asset_data_provider': asset_data_provider,
                    'force_update': True,
                    'dry_run': True
                }
            )

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_sync_push_error_handling_raises_not_implemented(self):
        """Test that sync_push with invalid asset data raises NotImplementedError."""
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {}

        asset_ids = ['test-asset-1']

        with self.assertRaises(NotImplementedError):
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={
                    'asset_data_provider': asset_data_provider,
                    'dry_run': True
                }
            )

    def test_sync_push_partial_success_raises_not_implemented(self):
        """Test that sync_push raises NotImplementedError (CKAN connector is harvest-only)."""
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {
                'id': asset_id,
                'name': f'Test Asset {asset_id}',
                'description': 'Valid asset',
                'key': f'test-asset-{uuid.uuid4().hex[:8]}',
            }

        asset_ids = ['asset-1', 'asset-2']

        with self.assertRaises(NotImplementedError) as context:
            self.connector.sync_push(
                asset_ids=asset_ids,
                options={
                    'asset_data_provider': asset_data_provider,
                    'dry_run': True
                }
            )

        self.assertIn("harvest-only", str(context.exception).lower())
        self.assertIn("pull only", str(context.exception).lower())

    def test_sync_operations_connection_error(self):
        """Test that sync operations handle connection errors gracefully."""
        invalid_connector = CKANConnector(base_url='https://invalid-ckan-instance-xyz-12345.com')

        # Test sync_pull - should return FAILED status, not raise exception
        result = invalid_connector.sync_pull(options={'limit': 1})
        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.FAILED)
        self.assertGreater(len(result.errors), 0)

        # Test sync_push - should raise NotImplementedError (harvest-only)
        def asset_data_provider(asset_id: str) -> Dict[str, Any]:
            return {'id': asset_id, 'name': 'Test'}

        with self.assertRaises(NotImplementedError):
            invalid_connector.sync_push(
                asset_ids=['test'],
                options={'asset_data_provider': asset_data_provider}
            )

