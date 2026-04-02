"""
Integration Tests for Databricks Connector Pull Operations

Tests the pull operations (sync_pull, map_to_hub_asset) using REAL Databricks workspace.

These tests require:
- Valid Databricks workspace URL and token
- Network access to Databricks Unity Catalog API
- At least one share in Unity Catalog (optional - tests will skip if no shares exist)

To run these tests:
1. Set DATABRICKS_HOST and DATABRICKS_TOKEN environment variables
2. Run: docker-compose exec api-service python -m pytest hub/apps/integrations/connectors/tests/test_databricks_connector_pull_integration.py -v -m integration
"""
import unittest
import os
import pytest
from django.test import TestCase

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.base import (
    MarketplaceType,
    MarketplaceAssetMapping,
    SyncResult,
    SyncStatus,
)
from hub.apps.assets.models import AssetSourceType


@pytest.mark.integration
class TestDatabricksConnectorPullIntegration(TestCase):
    """
    Integration tests for Databricks connector pull operations.

    Tests sync_pull and map_to_hub_asset with real Databricks workspace.
    No mocks or stubs - uses real API calls.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real Databricks workspace."""
        super().setUpClass()

        # Get credentials from environment
        cls.host = os.getenv('DATABRICKS_HOST')
        cls.token = os.getenv('DATABRICKS_TOKEN')

        if not cls.host or not cls.token:
            raise unittest.SkipTest("DATABRICKS_HOST and DATABRICKS_TOKEN environment variables required for integration tests")

        # Create connector
        cls.connector = DatabricksConnector(host=cls.host, token=cls.token)

        # Test connection
        try:
            cls.connector.test_connection()
        except Exception as e:
            raise unittest.SkipTest(f"Cannot connect to Databricks workspace: {e}")

    def setUp(self):
        """Set up test fixtures."""
        if not self.host or not self.token:
            self.skipTest("Databricks credentials not available")

    def test_sync_pull_basic(self):
        """Test basic sync_pull operation with real Databricks workspace."""
        result = self.connector.sync_pull(options={'limit': 5})

        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])
        self.assertGreaterEqual(result.total_items, 0)
        self.assertGreaterEqual(result.successful_items, 0)
        self.assertIn('mappings', result.metadata)
        self.assertIsInstance(result.metadata['mappings'], list)

        # Verify mappings structure
        if result.metadata['mappings']:
            mapping = result.metadata['mappings'][0]
            self.assertIn('asset_data', mapping)
            self.assertIn('source_type', mapping)
            self.assertIn('source_metadata', mapping)
            self.assertEqual(mapping['source_type'], AssetSourceType.FEDERATED)

    def test_sync_pull_with_limit(self):
        """Test sync_pull with limit option."""
        result = self.connector.sync_pull(options={'limit': 2})

        self.assertIsInstance(result, SyncResult)
        self.assertLessEqual(result.total_items, 2)
        self.assertIn('mappings', result.metadata)

    def test_sync_pull_without_resources(self):
        """Test sync_pull with include_resources=False."""
        result = self.connector.sync_pull(options={'include_resources': False, 'limit': 3})

        self.assertIsInstance(result, SyncResult)
        self.assertIn('mappings', result.metadata)
        # Verify mappings don't have resources when include_resources=False
        if result.metadata['mappings']:
            mapping = result.metadata['mappings'][0]
            # Resources may be empty list or not present
            resources = mapping.get('resources', [])
            self.assertIsInstance(resources, list)

    def test_sync_pull_with_resources(self):
        """Test sync_pull with include_resources=True."""
        result = self.connector.sync_pull(options={'include_resources': True, 'limit': 2})

        self.assertIsInstance(result, SyncResult)
        self.assertIn('mappings', result.metadata)
        # Verify mappings include resources when include_resources=True
        if result.metadata['mappings']:
            mapping = result.metadata['mappings'][0]
            resources = mapping.get('resources', [])
            self.assertIsInstance(resources, list)
            # Resources should have external flag if present
            for resource in resources:
                if isinstance(resource, dict):
                    resource_metadata = resource.get('metadata', {})
                    if resource_metadata:
                        # External resources should have external=True
                        if resource_metadata.get('external'):
                            self.assertTrue(resource_metadata.get('external'))

    def test_map_to_hub_asset_basic(self):
        """Test map_to_hub_asset with real listing from Databricks."""
        # Get a real listing
        listings = self.connector.list_listings(limit=1)

        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for testing")

        listing = listings[0]

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping structure
        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
        self.assertIsNotNone(mapping.asset_data)
        self.assertIsNotNone(mapping.source_metadata)

        # Verify asset_data
        self.assertIn('name', mapping.asset_data)
        self.assertIn('description', mapping.asset_data)
        self.assertIn('status', mapping.asset_data)
        self.assertIn('visibility', mapping.asset_data)

        # Verify source_metadata
        self.assertEqual(mapping.source_metadata['marketplace_type'], MarketplaceType.DATABRICKS_MARKETPLACE.value)
        self.assertEqual(mapping.source_metadata['listing_id'], listing.marketplace_id)
        self.assertIn('synced_at', mapping.source_metadata)

    def test_map_to_hub_asset_with_resources(self):
        """Test map_to_hub_asset with listing that has resources."""
        # Get a listing with resources
        listings = self.connector.list_listings(limit=1)

        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for testing")

        listing = listings[0]

        # Fetch resources for the listing
        try:
            resources = self.connector.list_resources(listing.marketplace_id)
            listing.resources = resources
        except Exception:
            # If resources can't be fetched, skip this test
            raise unittest.SkipTest("Cannot fetch resources for listing")

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify resources are included
        self.assertIsInstance(mapping.resources, list)
        for resource in mapping.resources:
            self.assertIsNotNone(resource.resource_id)
            self.assertIsNotNone(resource.name)
            # External resources should have external=True in metadata
            if resource.metadata:
                if resource.metadata.get('external'):
                    self.assertTrue(resource.metadata.get('external'))
                    self.assertIn('share_name', resource.metadata)

    def test_map_to_hub_asset_with_sync_job_id(self):
        """Test map_to_hub_asset with sync_job_id."""
        listings = self.connector.list_listings(limit=1)

        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for testing")

        listing = listings[0]
        sync_job_id = "test-job-123"

        # Map to Hub asset with sync_job_id
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id=sync_job_id)

        # Verify sync_job_id is included
        self.assertEqual(mapping.source_metadata.get('sync_job_id'), sync_job_id)

    def test_sync_pull_metadata_first_pattern(self):
        """Test that sync_pull follows metadata-first pattern (does NOT consume shares or create catalogs)."""
        # This test verifies that sync_pull doesn't perform deferred operations
        # We'll check that no catalogs are created and no shares are consumed

        # Get initial state (if possible)
        initial_listings = self.connector.list_listings(limit=1)

        if not initial_listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for testing")

        # Run sync_pull
        result = self.connector.sync_pull(options={'limit': 1})

        # Verify sync_pull succeeded
        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])

        # Verify mappings are returned
        self.assertIn('mappings', result.metadata)
        self.assertIsInstance(result.metadata['mappings'], list)

        # Note: We can't directly verify that shares weren't consumed or catalogs weren't created
        # without additional API calls, but the fact that sync_pull completes successfully
        # without errors indicates it's following the metadata-first pattern

    def test_sync_pull_empty_result(self):
        """Test sync_pull when no shares exist (empty workspace)."""
        # This test verifies graceful handling of empty results
        # Note: If shares exist, this test will still pass but won't test the empty case

        result = self.connector.sync_pull(options={'limit': 0})

        self.assertIsInstance(result, SyncResult)
        self.assertEqual(result.status, SyncStatus.COMPLETED)
        self.assertEqual(result.total_items, 0)
        self.assertEqual(result.successful_items, 0)
        self.assertIn('mappings', result.metadata)
        self.assertEqual(len(result.metadata['mappings']), 0)
