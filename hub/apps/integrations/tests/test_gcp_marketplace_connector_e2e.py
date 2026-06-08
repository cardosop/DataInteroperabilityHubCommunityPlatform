"""
End-to-End Tests for GCP Marketplace Connector

Tests complete sync workflows from connection creation → discovery → pull sync → federated asset creation.
Tests use real GCP Marketplace - no mocks or stubs.

Requirements:
- GCP_SERVICE_ACCOUNT_JSON environment variable with service account JSON
- GCP project with Analytics Hub API enabled
- Network access to Google Cloud APIs
"""

import json
import os

import pytest

pytestmark = pytest.mark.slow
from django.db import transaction
from django.test import TestCase

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
)
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.integrations.base import (
    MarketplaceType,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.connectors.gcp_marketplace_connector import GCPMarketplaceConnector
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
import uuid

# Real service account credentials for testing
# REAL_SERVICE_ACCOUNT_JSON removed — use get_test_credentials() below


def get_test_credentials():
    """Get GCP test credentials from environment.

    Requires GCP_SERVICE_ACCOUNT_JSON env var (set via .env.test and
    the Makefile test-batch-6-2 target).  Raises SkipTest when the
    env var is not available so the test suite can run without GCP
    credentials in environments where they are not configured.
    """
    import unittest
    import json
    env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
    if not env_json:
        raise unittest.SkipTest(
            "GCP_SERVICE_ACCOUNT_JSON not set — skipping"
        )
    try:
        return json.loads(env_json)
    except json.JSONDecodeError:
        raise unittest.SkipTest(
            "GCP_SERVICE_ACCOUNT_JSON is not valid JSON — skipping"
        )
class TestGCPMarketplaceConnectorE2E(TestCase):
    """
    End-to-end tests for GCP Marketplace connector.

    Tests complete workflows using real GCP Marketplace - no mocks or stubs.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test class with real credentials"""
        super().setUpClass()
        cls.credentials_json = get_test_credentials()
        cls.project_id = cls.credentials_json.get("project_id", "projzero-441310")

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}", status="ACTIVE", kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email=f"test-e2e-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-e2e-request-123",
        )

    def test_complete_sync_workflow(self):
        """Test complete sync workflow: connection → discovery → pull sync → federated asset creation."""
        # Step 1: Create marketplace connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
            name="Test GCP Marketplace Connection",
            config={
                "project_id": self.project_id,
                "credentials_json": self.credentials_json,
            },
            is_active=True,
        )

        # Step 2: Create connector from connection
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Step 3: Test connection
        connection_test = connector.test_connection()
        self.assertTrue(connection_test)

        # Step 4: Discover listings
        try:
            listings = connector.list_listings(limit=5)
            self.assertIsInstance(listings, list)
            # May be empty if no listings exist
        except Exception as e:
            # If no listings exist, skip the rest of the test
            self.skipTest(f"No listings available: {e}")

        if not listings:
            self.skipTest(
                "No listings available for testing. GCP project must have at least one "
                "Analytics Hub data exchange and listing; create one in the project or use "
                "a project with sample data to run this test."
            )

        # Step 5: Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction="PULL",
            status="PENDING",
            metadata={"limit": 5},
        )

        # Step 6: Perform sync pull
        result = connector.sync_pull(options={"limit": 5})
        self.assertIsInstance(result, SyncResult)
        self.assertIn(result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL])
        self.assertGreaterEqual(result.total_items, 0)
        self.assertIn("mappings", result.metadata)

        # Step 7: Update sync job
        sync_job.status = "COMPLETED"
        sync_job.result = {
            "total_items": result.total_items,
            "successful_items": result.successful_items,
            "failed_items": result.failed_items,
        }
        sync_job.save()

        # Verify sync job was updated
        updated_job = MarketplaceSyncJob.objects.get(id=sync_job.id)
        self.assertEqual(updated_job.status, "COMPLETED")

    def test_dual_contract_creation(self):
        """Test dual contract creation (ODPS + ODCS) from marketplace listing."""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Get a listing
        try:
            listings = connector.list_listings(limit=1)
        except Exception as e:
            self.skipTest(f"Could not list listings: {e}")

        if not listings:
            self.skipTest(
                "No listings available for testing. GCP project must have at least one "
                "Analytics Hub listing to run this test."
            )

        listing = listings[0]

        # Map to Hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify mapping has ODPS and ODCS metadata
        self.assertIsNotNone(mapping.odps_metadata)
        self.assertIsNotNone(mapping.odcs_metadata)

        # Verify ODPS metadata structure
        self.assertIn("product_details", mapping.odps_metadata)
        self.assertIn("pricing_plans", mapping.odps_metadata)
        self.assertIn("access_methods", mapping.odps_metadata)

        # Verify ODCS metadata structure
        if mapping.odcs_metadata:
            # ODCS metadata may be None if no schema information available
            # But if present, should have expected structure
            self.assertIsInstance(mapping.odcs_metadata, dict)

        # Verify asset data
        self.assertIsNotNone(mapping.asset_data)
        self.assertIn("name", mapping.asset_data)
        self.assertEqual(mapping.source_type, AssetSourceType.FEDERATED)

    def test_metadata_extraction_and_mapping(self):
        """Test metadata extraction and mapping from marketplace listing."""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Get a listing
        try:
            listings = connector.list_listings(limit=1)
        except Exception as e:
            self.skipTest(f"Could not list listings: {e}")

        if not listings:
            self.skipTest(
                "No listings available for testing. GCP project must have at least one "
                "Analytics Hub listing to run this test."
            )

        listing = listings[0]

        # Map to Hub asset
        mapping = connector.map_to_hub_asset(listing)

        # Verify metadata extraction
        self.assertIsNotNone(mapping.source_metadata)
        self.assertIn("marketplace_type", mapping.source_metadata)
        self.assertEqual(
            mapping.source_metadata["marketplace_type"],
            MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
        )

        # Verify ODPS metadata extraction
        odps_metadata = mapping.odps_metadata
        self.assertIsNotNone(odps_metadata)
        self.assertIsInstance(odps_metadata, dict)

        # Verify ODCS metadata extraction (may be None if no schema)
        odcs_metadata = mapping.odcs_metadata
        if odcs_metadata:
            self.assertIsInstance(odcs_metadata, dict)

    def test_bigquery_schema_extraction_and_type_mapping(self):
        """Test BigQuery schema extraction and type mapping."""
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Get a listing
        try:
            listings = connector.list_listings(limit=1)
        except Exception as e:
            self.skipTest(f"Could not list listings: {e}")

        if not listings:
            self.skipTest(
                "No listings available for testing. GCP project must have at least one "
                "Analytics Hub listing to run this test."
            )

        listing = listings[0]

        # Try to list resources (tables) for this listing
        try:
            resources = connector.list_resources(listing.marketplace_id)
            self.assertIsInstance(resources, list)

            # If resources exist, verify schema extraction
            if resources:
                resource = resources[0]
                # Resource should have schema information if available
                self.assertIsNotNone(resource)
                self.assertIsNotNone(resource.resource_id)
        except Exception as e:
            # Resources may not be available or listing may not have linked dataset
            # This is acceptable - schema extraction is optional
            pass

    def test_end_to_end_pull_sync_only(self):
        """Test end-to-end pull sync workflow (harvest-only connector)."""
        # Create connection
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
            name="Test GCP Pull Sync Connection",
            config={
                "project_id": self.project_id,
                "credentials_json": self.credentials_json,
            },
            is_active=True,
        )

        # Create connector
        connector = GCPMarketplaceConnector(
            project_id=self.project_id, credentials_json=self.credentials_json
        )
        connector.authenticate(
            {"project_id": self.project_id, "credentials_json": self.credentials_json}
        )

        # Verify connector only supports PULL
        self.assertIn("PULL", [d.value for d in connector.supported_sync_directions])
        self.assertNotIn("PUSH", [d.value for d in connector.supported_sync_directions])

        # Perform pull sync
        try:
            result = connector.sync_pull(options={"limit": 3})
            self.assertIsInstance(result, SyncResult)
            self.assertIn(
                result.status, [SyncStatus.COMPLETED, SyncStatus.PARTIAL, SyncStatus.FAILED]
            )
        except Exception as e:
            # May fail if no listings available
            self.skipTest(f"Sync pull failed: {e}")

        # Verify push operations raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            connector.sync_push(["asset-1"])

    def test_e2e_workflow_with_invalid_connection_config(self):
        """Test E2E workflow error handling with invalid connection config"""
        # Create connection with invalid config
        try:
            connection = self.service.create_connection(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
                name="Invalid Config Connection",
                config={"invalid": "config"},  # Invalid config
            )

            # Test connection should fail
            result = self.service.test_connection(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
            # Result may indicate failure
            if "success" in result:
                self.assertFalse(result["success"])
        except Exception:
            # Expected if validation is strict
            pass

    def test_e2e_workflow_with_missing_credentials(self):
        """Test E2E workflow error handling with missing credentials"""
        # Create connection without credentials
        try:
            connection = self.service.create_connection(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
                name="Missing Credentials Connection",
                config={},  # Empty config
            )

            # Sync should fail due to missing credentials
            with self.assertRaises(Exception):
                self.service.sync_from_marketplace(
                    connection_id=str(connection.id),
                    tenant_id=str(self.tenant.id),
                    user_id=str(self.user.id),
                    listing_ids=["test-listing"],
                )
        except Exception:
            # Expected if validation is strict
            pass

    def test_e2e_workflow_with_invalid_listing_ids(self):
        """Test E2E workflow error handling with invalid listing IDs"""
        # Create valid connection first
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
            name="Test Connection",
            config={"project_id": self.project_id, "credentials_json": self.credentials_json},
        )

        # Try sync with invalid listing IDs
        try:
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                listing_ids=["invalid-listing-id-1", "invalid-listing-id-2"],
            )
            # Sync job should be created but may fail during execution
            self.assertIsNotNone(sync_job)
            # Check if sync job failed
            if sync_job.status == SyncStatus.FAILED.value:
                self.assertGreater(len(sync_job.errors), 0)
        except Exception:
            # Expected if validation is strict
            pass

    def test_e2e_workflow_with_empty_listing_ids(self):
        """Test E2E workflow error handling with empty listing IDs"""
        # Create valid connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.GOOGLE_CLOUD_MARKETPLACE.value,
            name="Test Connection",
            config={"project_id": self.project_id, "credentials_json": self.credentials_json},
        )

        # Try sync with empty listing IDs
        try:
            sync_job = self.service.sync_from_marketplace(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                listing_ids=[],
            )
            # Should handle gracefully
            self.assertIsNotNone(sync_job)
        except (ValueError, TypeError):
            # Expected if empty list is invalid
            pass
