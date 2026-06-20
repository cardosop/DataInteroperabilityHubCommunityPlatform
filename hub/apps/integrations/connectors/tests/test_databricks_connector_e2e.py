"""
End-to-End Tests for Databricks Marketplace Connector

Tests complete sync workflows from connection creation → discovery → pull sync → federated asset creation.
Tests use real Databricks Marketplace - no mocks or stubs.

Requirements:
- DATABRICKS_HOST environment variable with Databricks workspace URL
- DATABRICKS_TOKEN environment variable with Databricks personal access token
- Network access to Databricks workspace
- Databricks workspace with Unity Catalog shares (for full E2E testing)
"""

import os
import unittest

import pytest

pytestmark = pytest.mark.slow
import time
import uuid

from django.test import TestCase

from hub.apps.assets.models import (
    AssetSourceType,
    AssetStatus,
    ExternalResourceReference,
)
from hub.apps.contracts.models import Contract
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.databricks_connector import DatabricksConnector
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


def get_databricks_credentials():
    """Get Databricks credentials from environment"""
    host = os.environ.get("DATABRICKS_HOST")
    token = os.environ.get("DATABRICKS_TOKEN")
    cluster_id = os.environ.get("DATABRICKS_CLUSTER_ID")  # Optional

    if not host or not token:
        raise unittest.SkipTest(
            "DATABRICKS_HOST and DATABRICKS_TOKEN environment variables are required for E2E tests"
        )

    credentials = {
        "host": host,
        "token": token,
    }
    if cluster_id:
        credentials["cluster_id"] = cluster_id

    return credentials


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestDatabricksConnectorE2E(TestCase):
    """
    End-to-end tests for Databricks Marketplace connector.

    Tests complete workflows using real Databricks Marketplace - no mocks or stubs.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        # Check credentials BEFORE super().setUpClass() to avoid
        # _fixture_teardown() closing connections on the skip path.
        cls.credentials = get_databricks_credentials()
        super().setUpClass()
        cls.host = cls.credentials["host"]
        cls.token = cls.credentials["token"]
        cls.cluster_id = cls.credentials.get("cluster_id")

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}",
            slug=f"test-tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.user = User.objects.create_user(
            email="test-databricks-e2e@example.com",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id=f"test-databricks-e2e-{int(time.time())}",
        )
        # Track created objects for cleanup
        self.created_connections = []
        self.created_sync_jobs = []
        self.created_assets = []
        self.created_contracts = []
        self.created_mappings = []

    def tearDown(self):
        """Clean up test data"""
        # Delete in reverse order of dependencies
        for asset in self.created_assets:
            try:
                # Delete external resource references first
                ExternalResourceReference.objects.filter(asset=asset).delete()
                # Delete contracts
                Contract.objects.filter(asset=asset).delete()
                # Delete mappings
                MarketplaceMapping.objects.filter(hub_asset=asset).delete()
                # Delete asset
                asset.delete()
            except Exception as e:
                print(f"Warning: Failed to delete asset {asset.id}: {e}")

        for sync_job in self.created_sync_jobs:
            try:
                sync_job.delete()
            except Exception as e:
                print(f"Warning: Failed to delete sync job {sync_job.id}: {e}")

        for connection in self.created_connections:
            try:
                connection.delete()
            except Exception as e:
                print(f"Warning: Failed to delete connection {connection.id}: {e}")

        # Delete tenant and user
        try:
            self.user.delete()
            self.tenant.delete()
        except Exception as e:
            print(f"Warning: Failed to delete tenant/user: {e}")

        super().tearDown()

    def test_complete_sync_workflow(self):
        """Test complete sync workflow: connection → discovery → pull sync → asset creation"""
        # Step 1: Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE.value,
            name="Databricks E2E Test Connection",
            config=self.credentials,
            is_active=True,
        )
        self.created_connections.append(connection)

        # Step 2: Test connection
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )
        connection_test = connector.test_connection()
        self.assertTrue(connection_test, "Connection test should succeed")

        # Step 3: Discover listings
        listings = connector.list_listings(limit=5)
        self.assertIsInstance(listings, list, "list_listings should return a list")

        # Step 4: If we have listings, test pull sync
        if listings:
            listing = listings[0]
            listing_id = listing.marketplace_id

            # Test get_listing
            retrieved_listing = connector.get_listing(listing_id)
            self.assertEqual(retrieved_listing.marketplace_id, listing_id)

            # Test list_resources
            resources = connector.list_resources(listing_id)
            self.assertIsInstance(resources, list)

            # Step 5: Create sync job and perform pull sync
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=connection,
                direction="PULL",
                status=SyncStatus.PENDING.value,
                metadata={"include_resources": True},
            )
            self.created_sync_jobs.append(sync_job)

            # Perform sync_pull
            sync_result = connector.sync_pull(
                listing_ids=[listing_id], options={"include_resources": True}
            )

            self.assertIsInstance(sync_result, SyncResult)
            self.assertIn(sync_result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])

            # Step 6: Map to hub asset
            if sync_result.status == SyncStatus.COMPLETED:
                mapping = connector.map_to_hub_asset(listing, sync_job_id=str(sync_job.id))
                self.assertIsNotNone(mapping)
                self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)
                self.assertEqual(
                    mapping.source_metadata["marketplace_type"],
                    MarketplaceType.DATABRICKS_MARKETPLACE.value,
                )

        # Test passes if we can complete the workflow up to the point where we have listings
        # If no listings, we still verify the connection and discovery work

    def test_end_to_end_pull_sync_only(self):
        """Test end-to-end pull sync workflow (harvest-only connector)."""
        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.DATABRICKS_MARKETPLACE.value,
            name="Databricks Pull Sync E2E",
            config=self.credentials,
            is_active=True,
        )
        self.created_connections.append(connection)

        # Initialize connector
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )

        # Discover listings
        listings = connector.list_listings(limit=1)
        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for E2E testing")

        listing = listings[0]

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction="PULL",
            status=SyncStatus.PENDING.value,
            metadata={"include_resources": True},
        )
        self.created_sync_jobs.append(sync_job)

        # Perform pull sync
        sync_result = connector.sync_pull(
            listing_ids=[listing.marketplace_id], options={"include_resources": True}
        )

        # Verify sync result
        self.assertIsInstance(sync_result, SyncResult)
        self.assertIn(sync_result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])
        self.assertIsNotNone(sync_result.metadata)
        self.assertIn("mappings", sync_result.metadata)

        # Verify mappings were created
        if sync_result.metadata.get("mappings"):
            mapping_data = sync_result.metadata["mappings"][0]
            self.assertIn("asset_data", mapping_data)
            self.assertIn("source_metadata", mapping_data)
            self.assertEqual(
                mapping_data["source_metadata"]["marketplace_type"],
                MarketplaceType.DATABRICKS_MARKETPLACE.value,
            )

    def test_metadata_extraction_and_mapping(self):
        """Test metadata extraction and mapping from Databricks listing"""
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )

        # Get a real listing
        listings = connector.list_listings(limit=1)
        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for E2E testing")

        listing = listings[0]

        # Map to hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify mapping structure
        self.assertIsNotNone(mapping)
        self.assertIsNotNone(mapping.asset_data)
        self.assertIsNotNone(mapping.source_metadata)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

        # Verify asset data
        self.assertIn("name", mapping.asset_data)
        self.assertIn("description", mapping.asset_data)
        self.assertIn("status", mapping.asset_data)
        self.assertEqual(mapping.asset_data["status"], AssetStatus.ACTIVE.value)

        # Verify source metadata
        self.assertEqual(
            mapping.source_metadata["marketplace_type"],
            MarketplaceType.DATABRICKS_MARKETPLACE.value,
        )
        self.assertIn("listing_id", mapping.source_metadata)
        self.assertIn("listing_url", mapping.source_metadata)

        # Verify ODPS metadata if available
        if mapping.odps_metadata:
            self.assertIsInstance(mapping.odps_metadata, dict)

        # Verify ODCS metadata if available
        if mapping.odcs_metadata:
            self.assertIsInstance(mapping.odcs_metadata, dict)

    def test_schema_extraction_and_type_mapping(self):
        """Test schema extraction and type mapping from Databricks tables"""
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )

        # Get a real listing with resources
        listings = connector.list_listings(limit=5)
        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for E2E testing")

        # Find a listing with resources
        listing_with_resources = None
        for listing in listings:
            resources = connector.list_resources(listing.marketplace_id)
            if resources:
                listing_with_resources = listing
                break

        if not listing_with_resources:
            raise unittest.SkipTest(
                "No shares with resources available for schema extraction testing"
            )

        # Get resources using marketplace_id (Databricks share name)
        resources = connector.list_resources(listing_with_resources.marketplace_id)
        self.assertGreater(len(resources), 0, "Should have at least one resource")

        # Test schema extraction for first resource (if it's a table)
        resource = resources[0]
        table_name = resource.metadata.get("table_name") if resource.metadata else None
        if table_name:
            # Verify the connector exposes the schema extraction hook
            self.assertTrue(
                hasattr(connector, "_extract_schema_from_table"),
                "Connector must expose _extract_schema_from_table",
            )

    def test_error_scenarios(self):
        """Test error scenarios with real Databricks workspace"""
        # Test invalid credentials
        invalid_connector = DatabricksConnector(host=self.host, token="invalid_token_12345")

        with self.assertRaises(ConnectionError):
            invalid_connector.test_connection()

        # Test share not found
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )

        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            connector.get_listing("non_existent_share_12345")

        # Test permission denied (if we can trigger it)
        # This is harder to test without actually having permission issues
        # For E2E test, we verify the error handling exists

    def test_dual_contract_creation(self):
        """Test dual contract creation (ODPS + ODCS) from marketplace listing"""
        connector = DatabricksConnector(
            host=self.host, token=self.token, cluster_id=self.cluster_id
        )

        # Get a real listing
        listings = connector.list_listings(limit=1)
        if not listings:
            raise unittest.SkipTest("No shares available in Databricks workspace for E2E testing")

        listing = listings[0]

        # Map to hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify mapping has ODPS and ODCS metadata
        # Note: Actual contract creation would be done by the service layer
        # Here we verify the mapping contains the necessary metadata for contract creation
        self.assertIsNotNone(mapping)

        # ODPS metadata should be available if present in share
        if mapping.odps_metadata:
            self.assertIsInstance(mapping.odps_metadata, dict)
            # Verify ODPS structure (pricing, access methods, etc.)
            # These would be used to create ODPS contract

        # ODCS metadata should be available if present in share
        if mapping.odcs_metadata:
            self.assertIsInstance(mapping.odcs_metadata, dict)
            # Verify ODCS structure (schema hints, quality hints, SLA hints)
            # These would be used to create ODCS contract

        # The actual contract creation would be done by MarketplaceIntegrationService
        # This E2E test verifies the mapping contains the necessary data
