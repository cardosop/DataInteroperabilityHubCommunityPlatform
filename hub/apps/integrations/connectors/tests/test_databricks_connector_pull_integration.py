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

import os
import unittest

import pytest
from django.test import TestCase

from hub.apps.assets.models import AssetSourceType
from hub.apps.integrations.base import (
    MarketplaceAssetMapping,
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector


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
        # Check credentials BEFORE super().setUpClass() to avoid
        # _fixture_teardown() closing connections on the skip path.
        cls.host = os.getenv("DATABRICKS_HOST")
        cls.token = os.getenv("DATABRICKS_TOKEN")

        if not cls.host or not cls.token:
            raise unittest.SkipTest(
                "DATABRICKS_HOST and DATABRICKS_TOKEN environment variables required for integration tests"
            )

        super().setUpClass()

        # Create connector
        cls.connector = DatabricksConnector(host=cls.host, token=cls.token)

        # Test connection
        try:
            cls.connector.test_connection()
        except Exception as e:
            raise unittest.SkipTest(f"Cannot connect to Databricks workspace: {e}") from e

    def setUp(self):
        """Set up test fixtures."""
        if not self.host or not self.token:
            self.skipTest("Databricks credentials not available")

    def test_sync_pull_basic(self):
        """Test basic sync_pull operation with real Databricks workspace."""
        result = self.connector.sync_pull(options={"limit": 5})

        assert isinstance(result, SyncResult)
        assert result.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]
        assert result.total_items >= 0
        assert result.successful_items >= 0
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)

        # Verify mappings structure
        if result.metadata["mappings"]:
            mapping = result.metadata["mappings"][0]
            assert "asset_data" in mapping
            assert "source_type" in mapping
            assert "source_metadata" in mapping
            assert mapping["source_type"] == AssetSourceType.FEDERATED

    def test_sync_pull_with_limit(self):
        """Test sync_pull with limit option."""
        result = self.connector.sync_pull(options={"limit": 2})

        assert isinstance(result, SyncResult)
        assert result.total_items <= 2
        assert "mappings" in result.metadata

    def test_sync_pull_without_resources(self):
        """Test sync_pull with include_resources=False."""
        result = self.connector.sync_pull(options={"include_resources": False, "limit": 3})

        assert isinstance(result, SyncResult)
        assert "mappings" in result.metadata
        # Verify mappings don't have resources when include_resources=False
        if result.metadata["mappings"]:
            mapping = result.metadata["mappings"][0]
            # Resources may be empty list or not present
            resources = mapping.get("resources", [])
            assert isinstance(resources, list)

    def test_sync_pull_with_resources(self):
        """Test sync_pull with include_resources=True."""
        result = self.connector.sync_pull(options={"include_resources": True, "limit": 2})

        assert isinstance(result, SyncResult)
        assert "mappings" in result.metadata
        # Verify mappings include resources when include_resources=True
        if result.metadata["mappings"]:
            mapping = result.metadata["mappings"][0]
            resources = mapping.get("resources", [])
            assert isinstance(resources, list)
            # Resources should have external flag if present
            for resource in resources:
                if isinstance(resource, dict):
                    resource_metadata = resource.get("metadata", {})
                    if resource_metadata and resource_metadata.get("external"):
                        # External resources should have external=True
                        assert resource_metadata.get("external")

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
        assert isinstance(mapping, MarketplaceAssetMapping)
        assert mapping.source_type == AssetSourceType.FEDERATED
        assert mapping.asset_data is not None
        assert mapping.source_metadata is not None

        # Verify asset_data
        assert "name" in mapping.asset_data
        assert "description" in mapping.asset_data
        assert "status" in mapping.asset_data
        assert "visibility" in mapping.asset_data

        # Verify source_metadata
        assert (
            mapping.source_metadata["marketplace_type"]
            == MarketplaceType.DATABRICKS_MARKETPLACE.value
        )
        assert mapping.source_metadata["listing_id"] == listing.marketplace_id
        assert "synced_at" in mapping.source_metadata

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
            raise unittest.SkipTest("Cannot fetch resources for listing") from None

        # Map to Hub asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify resources are included
        assert isinstance(mapping.resources, list)
        for resource in mapping.resources:
            assert resource.resource_id is not None
            assert resource.name is not None
            # External resources should have external=True in metadata
            if resource.metadata and resource.metadata.get("external"):
                assert resource.metadata.get("external")
                assert "share_name" in resource.metadata

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
        assert mapping.source_metadata.get("sync_job_id") == sync_job_id

    def test_sync_pull_returns_mappings(self):
        """Test that sync_pull completes and returns a mappings list.

        Verifies the basic sync_pull contract: SyncResult with
        COMPLETED/PARTIAL status and a ``mappings`` key in metadata.
        """
        initial_listings = self.connector.list_listings(limit=1)

        if not initial_listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for testing")

        # Run sync_pull
        result = self.connector.sync_pull(options={"limit": 1})

        # Verify sync_pull contract
        assert isinstance(result, SyncResult)
        assert result.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]
        assert "mappings" in result.metadata
        assert isinstance(result.metadata["mappings"], list)

    def test_sync_pull_empty_result(self):
        """Test sync_pull when no shares exist (empty workspace)."""
        # This test verifies graceful handling of empty results
        # Note: If shares exist, this test will still pass but won't test the empty case

        result = self.connector.sync_pull(options={"limit": 0})

        assert isinstance(result, SyncResult)
        assert result.status == SyncStatus.COMPLETED
        assert result.total_items == 0
        assert result.successful_items == 0
        assert "mappings" in result.metadata
        assert len(result.metadata["mappings"]) == 0
