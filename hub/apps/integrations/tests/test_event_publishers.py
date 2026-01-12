"""
Unit tests for MarketplaceEventPublisher.

Tests event publishing functionality using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import User, UserStatus
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.core.events.models import Event
from hub.apps.assets.models import Asset


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceEventPublisherUnitTest(TestCase):
    """Unit tests for MarketplaceEventPublisher using real EventPublisher."""

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

        # Create test connection
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True
        )

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type="FEDERATED"
        )

        # Create test sync job
        self.sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        # Create test mapping
        self.mapping = MarketplaceMapping.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            hub_asset=self.asset,
            external_listing_id="ext-listing-123",
            external_resource_ids=["res-1", "res-2"]
        )

    def test_publish_connection_created(self):
        """Test publishing marketplace.connection.created event."""
        event_id = self.publisher.publish_connection_created(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.created")
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["marketplace_type"], self.connection.marketplace_type)
        self.assertEqual(event.data["name"], self.connection.name)
        self.assertIn("created_at", event.data)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_publish_connection_updated(self):
        """Test publishing marketplace.connection.updated event."""
        changes = {
            "name": {"old": "Old Name", "new": "New Name"},
            "is_active": {"old": True, "new": False}
        }
        event_id = self.publisher.publish_connection_updated(
            connection_id=str(self.connection.id),
            changes=changes
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.updated")
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertIn("updated_at", event.data)

    def test_publish_connection_deleted(self):
        """Test publishing marketplace.connection.deleted event."""
        reason = "User requested deletion"
        event_id = self.publisher.publish_connection_deleted(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name,
            reason=reason
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.deleted")
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["marketplace_type"], self.connection.marketplace_type)
        self.assertEqual(event.data["name"], self.connection.name)
        self.assertEqual(event.data["reason"], reason)
        self.assertIn("deleted_at", event.data)

    def test_publish_sync_started(self):
        """Test publishing marketplace.sync.started event."""
        event_id = self.publisher.publish_sync_started(
            sync_job_id=str(self.sync_job.id),
            connection_id=str(self.connection.id),
            direction=self.sync_job.direction
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.started")
        self.assertEqual(event.data["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["direction"], self.sync_job.direction)
        self.assertIn("started_at", event.data)

    def test_publish_sync_completed(self):
        """Test publishing marketplace.sync.completed event."""
        items_synced = 10
        items_failed = 2
        event_id = self.publisher.publish_sync_completed(
            sync_job_id=str(self.sync_job.id),
            connection_id=str(self.connection.id),
            direction=self.sync_job.direction,
            status=SyncStatus.COMPLETED.value,
            items_synced=items_synced,
            items_failed=items_failed
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.completed")
        self.assertEqual(event.data["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["direction"], self.sync_job.direction)
        self.assertEqual(event.data["status"], SyncStatus.COMPLETED.value)
        self.assertEqual(event.data["items_synced"], items_synced)
        self.assertEqual(event.data["items_failed"], items_failed)
        self.assertIn("completed_at", event.data)

    def test_publish_sync_failed(self):
        """Test publishing marketplace.sync.failed event."""
        error_message = "Connection timeout"
        error_details = {"error_code": "TIMEOUT", "retry_count": 3}
        event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(self.sync_job.id),
            connection_id=str(self.connection.id),
            direction=self.sync_job.direction,
            error_message=error_message,
            error_details=error_details
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.failed")
        self.assertEqual(event.data["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["direction"], self.sync_job.direction)
        self.assertEqual(event.data["error_message"], error_message)
        self.assertEqual(event.data["error_details"], error_details)
        self.assertIn("failed_at", event.data)

    def test_publish_mapping_created(self):
        """Test publishing marketplace.mapping.created event."""
        event_id = self.publisher.publish_mapping_created(
            mapping_id=str(self.mapping.id),
            connection_id=str(self.connection.id),
            hub_asset_id=str(self.asset.id),
            external_listing_id=self.mapping.external_listing_id
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.created")
        self.assertEqual(event.data["mapping_id"], str(self.mapping.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["hub_asset_id"], str(self.asset.id))
        self.assertEqual(event.data["external_listing_id"], self.mapping.external_listing_id)
        self.assertIn("created_at", event.data)

    def test_publish_mapping_updated(self):
        """Test publishing marketplace.mapping.updated event."""
        changes = {
            "external_listing_id": {"old": "old-listing", "new": "new-listing"},
            "sync_metadata": {"old": {}, "new": {"last_sync": "2025-01-01"}}
        }
        event_id = self.publisher.publish_mapping_updated(
            mapping_id=str(self.mapping.id),
            connection_id=str(self.connection.id),
            changes=changes
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.updated")
        self.assertEqual(event.data["mapping_id"], str(self.mapping.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["changes"], changes)
        self.assertIn("updated_at", event.data)

    def test_publish_mapping_deleted(self):
        """Test publishing marketplace.mapping.deleted event."""
        reason = "Asset was deleted"
        event_id = self.publisher.publish_mapping_deleted(
            mapping_id=str(self.mapping.id),
            connection_id=str(self.connection.id),
            hub_asset_id=str(self.asset.id),
            external_listing_id=self.mapping.external_listing_id,
            reason=reason
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.deleted")
        self.assertEqual(event.data["mapping_id"], str(self.mapping.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["hub_asset_id"], str(self.asset.id))
        self.assertEqual(event.data["external_listing_id"], self.mapping.external_listing_id)
        self.assertEqual(event.data["reason"], reason)
        self.assertIn("deleted_at", event.data)

    def test_publish_connection_created_with_minimal_data(self):
        """Test publishing connection.created event with only required fields."""
        event_id = self.publisher.publish_connection_created(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.created")
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["marketplace_type"], self.connection.marketplace_type)
        self.assertEqual(event.data["name"], self.connection.name)

    def test_publish_sync_started_with_minimal_data(self):
        """Test publishing sync.started event with only required fields."""
        event_id = self.publisher.publish_sync_started(
            sync_job_id=str(self.sync_job.id),
            connection_id=str(self.connection.id),
            direction=self.sync_job.direction
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.started")
        self.assertEqual(event.data["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["direction"], self.sync_job.direction)

    def test_publish_sync_failed_with_minimal_data(self):
        """Test publishing sync.failed event with only required fields."""
        event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(self.sync_job.id),
            connection_id=str(self.connection.id),
            direction=self.sync_job.direction,
            error_message="Test error"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.failed")
        self.assertEqual(event.data["sync_job_id"], str(self.sync_job.id))
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertEqual(event.data["direction"], self.sync_job.direction)
        self.assertEqual(event.data["error_message"], "Test error")

    def test_event_source_includes_tenant_and_user(self):
        """Test that events include tenant_id and user_id in source."""
        event_id = self.publisher.publish_connection_created(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "marketplace_integration_service")

    def test_event_timestamp_is_set(self):
        """Test that events have timestamp set."""
        before_publish = timezone.now()
        event_id = self.publisher.publish_connection_created(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name
        )
        after_publish = timezone.now()

        event = Event.objects.get(event_id=event_id)
        self.assertIsNotNone(event.timestamp)
        # Verify timestamp is between before and after
        self.assertGreaterEqual(event.timestamp, before_publish)
        self.assertLessEqual(event.timestamp, after_publish)

    def test_publish_connection_deleted_without_reason(self):
        """Test publishing connection.deleted event without reason."""
        event_id = self.publisher.publish_connection_deleted(
            connection_id=str(self.connection.id),
            marketplace_type=self.connection.marketplace_type,
            name=self.connection.name
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.deleted")
        self.assertEqual(event.data["connection_id"], str(self.connection.id))
        self.assertIsNone(event.data.get("reason"))
        self.assertIn("deleted_at", event.data)

    def test_publish_mapping_deleted_without_reason(self):
        """Test publishing mapping.deleted event without reason."""
        event_id = self.publisher.publish_mapping_deleted(
            mapping_id=str(self.mapping.id),
            connection_id=str(self.connection.id),
            hub_asset_id=str(self.asset.id),
            external_listing_id=self.mapping.external_listing_id
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.deleted")
        self.assertEqual(event.data["mapping_id"], str(self.mapping.id))
        self.assertIsNone(event.data.get("reason"))
        self.assertIn("deleted_at", event.data)

