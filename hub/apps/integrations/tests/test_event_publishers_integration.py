"""
Integration tests for MarketplaceEventPublisher.

Tests event publishing integration with real services and database operations.
Verifies that events are properly published during actual service operations.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.core.events.models import Event
from hub.apps.assets.models import Asset


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceEventPublisherIntegrationTest(TestCase):
    """Integration tests for MarketplaceEventPublisher with real services."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create MarketplaceEventPublisher instance
        self.publisher = MarketplaceEventPublisher(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create service instance
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="test-request-123"
        )

        self.config = {
            "api_key": "test-api-key-123",
            "endpoint": "https://api.example.com",
            "timeout": 30
        }

    def test_publish_connection_events_integration(self):
        """Test publishing connection events during actual connection operations."""
        # Create connection using service
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Integration Test Connection",
            config=self.config
        )

        # Verify connection.created event was published by service
        events = Event.objects.filter(
            event_type="integration.connection.created"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        # Now test our MarketplaceEventPublisher methods
        # Update connection and publish event
        changes = {"name": {"old": "Integration Test Connection", "new": "Updated Connection"}}
        event_id = self.publisher.publish_connection_updated(
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.connection.updated event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.updated")
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["changes"], changes)

        # Delete connection and publish event
        event_id = self.publisher.publish_connection_deleted(
            connection_id=str(connection.id),
            marketplace_type=connection.marketplace_type,
            name=connection.name,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.connection.deleted event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.deleted")
        self.assertEqual(event.data["connection_id"], str(connection.id))

    def test_publish_sync_events_integration(self):
        """Test publishing sync events during actual sync operations."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Sync Test Connection",
            config=self.config
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        # Publish sync.started event
        event_id = self.publisher.publish_sync_started(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.sync.started event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.started")
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))

        # Update sync job status and publish completed event
        sync_job.status = SyncStatus.COMPLETED.value
        sync_job.save()

        event_id = self.publisher.publish_sync_completed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.sync.completed event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.completed")
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(event.data["items_synced"], 10)
        self.assertEqual(event.data["items_failed"], 0)

    def test_publish_mapping_events_integration(self):
        """Test publishing mapping events during actual mapping operations."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Mapping Test Connection",
            config=self.config
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type="FEDERATED"
        )

        # Create mapping using service
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify integration.mapping.created event was published by service
        events = Event.objects.filter(
            event_type="integration.mapping.created"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        # Now test our MarketplaceEventPublisher methods
        # Update mapping and publish event
        changes = {
            "external_listing_id": {"old": "ext-listing-123", "new": "ext-listing-456"}
        }
        event_id = self.publisher.publish_mapping_updated(
            mapping_id=str(mapping.id),
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.mapping.updated event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.updated")
        self.assertEqual(event.data["mapping_id"], str(mapping.id))
        self.assertEqual(event.data["changes"], changes)

        # Delete mapping and publish event
        event_id = self.publisher.publish_mapping_deleted(
            mapping_id=str(mapping.id),
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id=mapping.external_listing_id,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.mapping.deleted event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.deleted")
        self.assertEqual(event.data["mapping_id"], str(mapping.id))

    def test_publish_sync_failed_event_integration(self):
        """Test publishing sync.failed event during sync failure scenarios."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Failed Sync Test Connection",
            config=self.config
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.FAILED.value
        )

        # Publish sync.failed event
        error_message = "Connection timeout after 30 seconds"
        error_details = {
            "error_code": "TIMEOUT",
            "retry_count": 3,
            "last_attempt": timezone.now().isoformat()
        }
        event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            error_message=error_message,
            error_details=error_details,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace.sync.failed event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.failed")
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(event.data["error_message"], error_message)
        self.assertEqual(event.data["error_details"], error_details)

    def test_event_deduplication_works(self):
        """Test that event deduplication works correctly."""
        from django.conf import settings
        from hub.apps.core.events.deduplication import get_redis_client

        # Check if Redis is available for deduplication
        try:
            redis_client = get_redis_client()
            if redis_client:
                redis_client.ping()
                redis_available = True
            else:
                redis_available = False
        except Exception:
            # Redis unavailable - deduplication will be skipped (fail-open)
            redis_available = False

        # Publish same event twice
        event_id_1 = self.publisher.publish_connection_created(
            connection_id="test-connection-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        event_id_2 = self.publisher.publish_connection_created(
            connection_id="test-connection-123",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        if redis_available:
            # When Redis is available, deduplication should work
            # Verify both calls return the same event ID (deduplication)
            self.assertEqual(event_id_1, event_id_2, "Event deduplication should return same event ID when Redis is available")

            # Verify only one event exists in database
            events = Event.objects.filter(event_id=event_id_1)
            self.assertEqual(events.count(), 1, "Only one event should exist when deduplication works")
        else:
            # When Redis is unavailable, deduplication is skipped (fail-open behavior)
            # Events will be published separately, which is expected behavior
            # Verify both events were published successfully
            self.assertIsNotNone(event_id_1, "First event should be published even when Redis is unavailable")
            self.assertIsNotNone(event_id_2, "Second event should be published even when Redis is unavailable")

            # Both events should exist in database (deduplication skipped)
            events = Event.objects.filter(event_id__in=[event_id_1, event_id_2])
            self.assertEqual(events.count(), 2, "Both events should exist when deduplication is unavailable")

