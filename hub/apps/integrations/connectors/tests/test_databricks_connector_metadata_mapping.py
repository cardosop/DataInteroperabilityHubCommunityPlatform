"""
Unit tests for Databricks connector metadata mapping operations.

Tests map_to_hub_asset and verifies that push methods raise NotImplementedError.
"""
import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from django.test import TestCase

from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.base import (
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    MarketplaceAssetMapping,
)
from hub.apps.assets.models import AssetSourceType


class TestDatabricksConnectorMetadataMapping(TestCase):
    """Test metadata mapping operations."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com",
            token="test-token"
        )

    def test_map_to_hub_asset_complete_metadata(self):
        """Test map_to_hub_asset with complete metadata."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            description="Test description",
            category="test_category",
            tags=["tag1", "tag2"],
            metadata={
                "databricks_share": {
                    "name": "test_share",
                    "comment": "Test comment",
                    "owner": "test_owner",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-02T00:00:00Z"
                },
                "odps_metadata": {
                    "product": {
                        "name": "Test Product",
                        "description": "Product description"
                    },
                    "pricing_plans": [
                        {
                            "name": "Free",
                            "price": 0
                        }
                    ],
                    "access_methods": {
                        "api": {
                            "type": "REST"
                        }
                    },
                    "payment_gateways": {}
                },
                "odcs_metadata": {
                    "schema": {
                        "fields": [
                            {
                                "name": "col1",
                                "type": "string"
                            }
                        ]
                    },
                    "quality": {
                        "completeness": 0.95
                    },
                    "sla": {
                        "availability": "99.9%"
                    }
                }
            },
            url="https://test-workspace.cloud.databricks.com/#share/test_share"
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping structure
        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

        # Verify asset_data
        self.assertEqual(mapping.asset_data["name"], "Test Share")
        self.assertEqual(mapping.asset_data["description"], "Test description")
        self.assertEqual(mapping.asset_data["domain"], "test_category")
        self.assertEqual(mapping.asset_data["tags"], ["tag1", "tag2"])
        self.assertEqual(mapping.asset_data["status"], "ACTIVE")
        self.assertEqual(mapping.asset_data["visibility"], "PUBLIC")

        # Verify source_metadata
        self.assertEqual(mapping.source_metadata["marketplace_type"], MarketplaceType.DATABRICKS_MARKETPLACE.value)
        self.assertEqual(mapping.source_metadata["listing_id"], "test_share")
        self.assertIn("synced_at", mapping.source_metadata)
        self.assertIn("listing_url", mapping.source_metadata)

        # Verify ODPS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIn("product", mapping.odps_metadata)
        self.assertIn("pricing_plans", mapping.odps_metadata)

        # Verify ODCS metadata
        self.assertIsNotNone(mapping.odcs_metadata)
        self.assertIn("schema", mapping.odcs_metadata)
        self.assertIn("quality", mapping.odcs_metadata)
        self.assertIn("sla", mapping.odcs_metadata)

    def test_map_to_hub_asset_with_resources(self):
        """Test map_to_hub_asset with resources."""
        resources = [
            MarketplaceResource(
                resource_id="catalog.schema.table1",
                resource_type="TABLE",
                name="Table 1",
                description="Test table 1",
                format="DATABRICKS_TABLE"
            ),
            MarketplaceResource(
                resource_id="catalog.schema.table2",
                resource_type="TABLE",
                name="Table 2",
                description="Test table 2",
                format="DATABRICKS_TABLE"
            )
        ]

        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            resources=resources,
            metadata={
                "databricks_share": {
                    "name": "test_share"
                }
            }
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify resources
        self.assertEqual(len(mapping.resources), 2)
        for i, resource in enumerate(mapping.resources):
            self.assertEqual(resource.resource_id, resources[i].resource_id)
            self.assertEqual(resource.name, resources[i].name)
            self.assertTrue(resource.metadata.get("external"))
            self.assertEqual(resource.metadata.get("share_name"), "test_share")
            self.assertEqual(resource.metadata.get("table_name"), resources[i].resource_id)

    def test_map_to_hub_asset_domain_from_owner(self):
        """Test map_to_hub_asset extracts domain from share owner when category not available."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={
                "databricks_share": {
                    "name": "test_share",
                    "owner": "owner@example.com"
                }
            }
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify domain is extracted from owner
        self.assertEqual(mapping.asset_data["domain"], "owner@example.com")

    def test_map_to_hub_asset_with_sync_job_id(self):
        """Test map_to_hub_asset includes sync_job_id in source_metadata."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={
                "databricks_share": {
                    "name": "test_share"
                }
            }
        )

        sync_job_id = "job-123-456"

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing, sync_job_id=sync_job_id)

        # Verify sync_job_id is included
        self.assertEqual(mapping.source_metadata.get("sync_job_id"), sync_job_id)

    def test_map_to_hub_asset_listing_url_generation(self):
        """Test map_to_hub_asset generates listing_url when not provided."""
        listing = MarketplaceListing(
            marketplace_id="test_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Test Share",
            metadata={
                "databricks_share": {
                    "name": "test_share"
                }
            }
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify listing_url is generated
        expected_url = f"{self.connector.host}/#share/test_share"
        self.assertEqual(mapping.source_metadata["listing_url"], expected_url)

    def test_map_to_hub_asset_minimal_listing(self):
        """Test map_to_hub_asset with minimal listing data."""
        listing = MarketplaceListing(
            marketplace_id="minimal_share",
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE,
            title="Minimal Share",
            metadata={}
        )

        # Execute map_to_hub_asset
        mapping = self.connector.map_to_hub_asset(listing)

        # Verify mapping is created with defaults
        self.assertIsInstance(mapping, MarketplaceAssetMapping)
        self.assertEqual(mapping.asset_data["name"], "Minimal Share")
        self.assertEqual(mapping.asset_data["status"], "ACTIVE")
        self.assertEqual(mapping.asset_data["visibility"], "PUBLIC")
        self.assertIsNone(mapping.odps_metadata)
        self.assertIsNone(mapping.odcs_metadata)


class TestDatabricksConnectorPushOperations(TestCase):
    """Test that push operations raise NotImplementedError."""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.core.resilience.circuit_breaker import reset_circuit_breaker_by_name
        reset_circuit_breaker_by_name('databricks-connector')
        self.connector = DatabricksConnector(
            host="https://test-workspace.cloud.databricks.com",
            token="test-token"
        )

    def test_create_listing_raises_not_implemented(self):
        """Test create_listing() raises NotImplementedError."""
        listing_data = {
            "name": "test_share",
            "comment": "Test share"
        }

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.create_listing(listing_data)

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_update_listing_raises_not_implemented(self):
        """Test update_listing() raises NotImplementedError."""
        listing_data = {
            "comment": "Updated comment"
        }

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.update_listing("test_share", listing_data)

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_publish_resource_raises_not_implemented(self):
        """Test publish_resource() raises NotImplementedError."""
        resource_data = {
            "name": "test_table",
            "type": "TABLE"
        }

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.publish_resource("test_share", resource_data)

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_map_from_hub_asset_raises_not_implemented(self):
        """Test map_from_hub_asset() raises NotImplementedError."""
        asset_data = {
            "name": "Test Asset",
            "description": "Test description"
        }

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.map_from_hub_asset(asset_data)

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_sync_push_raises_not_implemented(self):
        """Test sync_push() raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1", "asset-2"])

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_sync_push_with_options_raises_not_implemented(self):
        """Test sync_push() with options raises NotImplementedError."""
        options = {
            "dry_run": True,
            "force_update": False
        }

        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push(["asset-1"], options)

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_sync_push_empty_list_raises_not_implemented(self):
        """Test sync_push() with empty list raises NotImplementedError."""
        with self.assertRaises(NotImplementedError) as cm:
            self.connector.sync_push([])

        self.assertIn("harvest-only", str(cm.exception).lower())
        self.assertIn("PULL", str(cm.exception))

    def test_supported_sync_directions_is_pull_only(self):
        """Test that supported_sync_directions only includes PULL."""
        from hub.apps.integrations.base import SyncDirection

        supported = self.connector.supported_sync_directions
        self.assertEqual(len(supported), 1)
        self.assertEqual(supported[0], SyncDirection.PULL)
        self.assertNotIn(SyncDirection.PUSH, supported)
        self.assertNotIn(SyncDirection.BIDIRECTIONAL, supported)
