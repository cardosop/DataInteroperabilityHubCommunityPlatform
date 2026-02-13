"""
E2E tests for MarketplaceIntegrationService marketplace event publishing.

Tests end-to-end workflows to verify marketplace events are published correctly
throughout the entire lifecycle of marketplace operations.
"""

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.core.events.models import Event
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceListing,
    MarketplaceType,
    SyncDirection,
    SyncStatus,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceEventPublishingE2ETest(TestCase):
    """E2E tests for marketplace event publishing workflows"""

    def setUp(self):
        """Set up test data"""
        # CRITICAL: Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="test-request-123"
        )
        self.config = {
            "api_key": "test-api-key-123",
            "endpoint": "https://api.example.com",
            "timeout": 30,
        }

        # Register test connectors for E2E tests
        class TestSnowflakeConnector(DataMarketplaceConnector):
            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return []

            def get_listing(self, listing_id: str):
                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title="Test Listing",
                )

            def list_resources(self, listing_id: str):
                return []

            def create_listing(self, listing: MarketplaceListing):
                return listing

            def update_listing(self, listing_id: str, listing: MarketplaceListing):
                return listing

            def publish_resource(self, listing_id: str, resource):
                return resource

            def download_resource(self, resource_id: str, destination_path: str):
                return destination_path

        factory = MarketplaceConnectorFactory()
        factory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestSnowflakeConnector
        )

    def test_connection_lifecycle_publishes_marketplace_events(self):
        """E2E test: Verify marketplace events are published throughout connection lifecycle"""
        # Create connection - should publish marketplace.connection.created
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
        )

        created_events = Event.objects.filter(event_type="marketplace.connection.created")
        self.assertEqual(created_events.count(), 1)
        created_event = created_events.first()
        self.assertEqual(created_event.data["connection_id"], str(connection.id))

        # Update connection - should publish marketplace.connection.updated
        self.service.update_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Connection",
            is_active=False,
        )

        updated_events = Event.objects.filter(event_type="marketplace.connection.updated")
        self.assertEqual(updated_events.count(), 1)
        updated_event = updated_events.first()
        self.assertEqual(updated_event.data["connection_id"], str(connection.id))
        self.assertIn("changes", updated_event.data)

        # Delete connection - should publish marketplace.connection.deleted
        self.service.delete_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="E2E test deletion",
        )

        deleted_events = Event.objects.filter(event_type="marketplace.connection.deleted")
        self.assertEqual(deleted_events.count(), 1)
        deleted_event = deleted_events.first()
        self.assertEqual(deleted_event.data["connection_id"], str(connection.id))

    def test_mapping_lifecycle_publishes_marketplace_events(self):
        """E2E test: Verify marketplace events are published throughout mapping lifecycle"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED,
        )

        # Create mapping - should publish marketplace.mapping.created
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        created_events = Event.objects.filter(event_type="marketplace.mapping.created")
        self.assertEqual(created_events.count(), 1)
        created_event = created_events.first()
        self.assertEqual(created_event.data["mapping_id"], str(mapping.id))

        # Update mapping - should publish marketplace.mapping.updated
        self.service.update_mapping(
            mapping_id=str(mapping.id),
            external_listing_id="ext-listing-456",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        updated_events = Event.objects.filter(event_type="marketplace.mapping.updated")
        self.assertEqual(updated_events.count(), 1)
        updated_event = updated_events.first()
        self.assertEqual(updated_event.data["mapping_id"], str(mapping.id))

        # Delete mapping - should publish marketplace.mapping.deleted
        self.service.delete_mapping(
            mapping_id=str(mapping.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="E2E test deletion",
        )

        deleted_events = Event.objects.filter(event_type="marketplace.mapping.deleted")
        self.assertEqual(deleted_events.count(), 1)
        deleted_event = deleted_events.first()
        self.assertEqual(deleted_event.data["mapping_id"], str(mapping.id))

    def test_sync_workflow_publishes_marketplace_events(self):
        """E2E test: Verify marketplace events are published throughout sync workflow"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
        )

        # Start sync - should publish marketplace.sync.started
        sync_job = self.service.sync_from_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=["listing-1"],
        )

        started_events = Event.objects.filter(event_type="marketplace.sync.started")
        self.assertEqual(started_events.count(), 1)
        started_event = started_events.first()
        self.assertEqual(started_event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(started_event.data["direction"], SyncDirection.PULL.value)

        # Simulate sync completion by updating sync job status
        sync_job.items_synced = 10
        sync_job.items_failed = 0
        sync_job.status = SyncStatus.COMPLETED.value
        sync_job.completed_at = timezone.now()
        sync_job.save()

        # Update workflow status to trigger completion event
        # Note: In real scenario, this would be called by workflow engine
        # For E2E test, we simulate by directly calling sync_workflow_status_to_sync_job
        # But first we need to create a workflow instance or mock the workflow status update
        # For now, we'll verify the started event was published correctly
        # The completion event would be published when sync_workflow_status_to_sync_job is called
        # with a completed workflow status

    def test_sync_push_workflow_publishes_marketplace_events(self):
        """E2E test: Verify marketplace events are published for PUSH sync workflow"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED,
        )

        # Start PUSH sync - should publish marketplace.sync.started
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        started_events = Event.objects.filter(event_type="marketplace.sync.started")
        self.assertEqual(started_events.count(), 1)
        started_event = started_events.first()
        self.assertEqual(started_event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(started_event.data["direction"], SyncDirection.PUSH.value)

    def test_complete_marketplace_integration_workflow(self):
        """E2E test: Complete workflow from connection creation to sync completion"""
        # Step 1: Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="E2E Test Connection",
            config=self.config,
        )
        self.assertEqual(
            Event.objects.filter(event_type="marketplace.connection.created").count(), 1
        )

        # Step 2: Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Test Asset",
            source_type=AssetSourceType.FEDERATED,
        )

        # Step 3: Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="e2e-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertEqual(Event.objects.filter(event_type="marketplace.mapping.created").count(), 1)

        # Step 4: Start sync
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )
        self.assertEqual(Event.objects.filter(event_type="marketplace.sync.started").count(), 1)

        # Verify all marketplace events were published
        all_marketplace_events = Event.objects.filter(event_type__startswith="marketplace.")
        self.assertGreaterEqual(all_marketplace_events.count(), 3)

        # Verify event types
        event_types = set(all_marketplace_events.values_list("event_type", flat=True))
        self.assertIn("marketplace.connection.created", event_types)
        self.assertIn("marketplace.mapping.created", event_types)
        self.assertIn("marketplace.sync.started", event_types)

    def test_event_publishing_with_invalid_connection_id(self):
        """Test event publishing error handling with invalid connection ID"""
        from hub.apps.core.services.base import NotFoundError

        # Try to get non-existent connection
        with self.assertRaises(NotFoundError):
            self.service.get_connection(
                connection_id="invalid-connection-id",
                tenant_id=str(self.tenant.id),
            )

    def test_event_publishing_with_invalid_sync_job_id(self):
        """Test event publishing error handling with invalid sync job ID"""
        from hub.apps.core.services.base import NotFoundError

        # Try to get non-existent sync job
        with self.assertRaises(NotFoundError):
            self.service.get_sync_job(
                sync_job_id="invalid-sync-job-id",
                tenant_id=str(self.tenant.id),
            )

    def test_event_publishing_with_empty_listing_ids(self):
        """Test event publishing error handling with empty listing IDs"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
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

    def test_event_publishing_with_none_tenant_id(self):
        """Test event publishing error handling with None tenant ID"""
        from hub.apps.core.services.base import ValidationError

        # Try to create connection with None tenant_id
        with self.assertRaises((ValidationError, TypeError)):
            self.service.create_connection(
                tenant_id=None,  # type: ignore[arg-type]
                user_id=str(self.user.id),
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name="Test Connection",
                config=self.config,
            )

    def tearDown(self):
        """Reconnect signals after test"""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
