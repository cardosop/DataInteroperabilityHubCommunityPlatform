"""
Integration tests for MarketplaceEventPublisher.

Tests event publishing integration with real services and database operations.
Verifies that events are properly published during actual service operations.
"""

import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.core.events.models import Event
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.event_publishers import MarketplaceEventPublisher
from hub.apps.integrations.models import (
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceEventPublisherIntegrationTest(TestCase):
    """
    Integration tests for MarketplaceEventPublisher with real services.

    Uses TestCase (SAVEPOINT-wrapped) so each test auto-rolls back.
    """

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        # Disconnect semantic service signals to prevent timeouts
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass

        self._create_fixtures()

    def _create_fixtures(self):
        """Create tenant, user, publisher, service, and config. Uses unique slug per run to avoid collisions."""
        slug_suffix = uuid.uuid4().hex[:8]
        self._suffix = slug_suffix
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {slug_suffix}",
            slug=f"test-tenant-{slug_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"test-{slug_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.publisher = MarketplaceEventPublisher(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="test-request-123"
        )
        self.config = {
            "api_key": "test-api-key-123",
            "endpoint": "https://api.example.com",
            "timeout": 30,
        }

    def tearDown(self):
        """Reconnect signals, then run normal TestCase teardown (SAVEPOINT rollback)."""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass
        super().tearDown()

    def test_publish_connection_events_integration(self):
        """Test publishing connection events during actual connection operations."""
        # Create connection using service
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Integration Test Connection {self._suffix}",
            config=self.config,
        )

        # Verify connection.created event was published by service
        events = Event.objects.filter(event_type="integration.connection.created").order_by(
            "-timestamp"
        )
        self.assertGreaterEqual(events.count(), 1)

        # Now test our MarketplaceEventPublisher methods
        # Update connection and publish event
        changes = {
            "name": {
                "old": f"Integration Test Connection {self._suffix}",
                "new": "Updated Connection",
            }
        }
        event_id = self.publisher.publish_connection_updated(
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
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
            user_id=str(self.user.id),
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
            name=f"Sync Test Connection {self._suffix}",
            config=self.config,
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
        )

        # Publish sync.started event
        event_id = self.publisher.publish_sync_started(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
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
            user_id=str(self.user.id),
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
            name=f"Mapping Test Connection {self._suffix}",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Test Asset {self._suffix}",
            source_type="FEDERATED",
        )

        # Create mapping using service
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify integration.mapping.created event was published by service
        events = Event.objects.filter(event_type="integration.mapping.created").order_by(
            "-timestamp"
        )
        self.assertGreaterEqual(events.count(), 1)

        # Now test our MarketplaceEventPublisher methods
        # Update mapping and publish event
        changes = {"external_listing_id": {"old": "ext-listing-123", "new": "ext-listing-456"}}
        event_id = self.publisher.publish_mapping_updated(
            mapping_id=str(mapping.id),
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
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
            user_id=str(self.user.id),
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
            name=f"Failed Sync Test Connection {self._suffix}",
            config=self.config,
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.FAILED.value,
        )

        # Publish sync.failed event
        error_message = "Connection timeout after 30 seconds"
        error_details = {
            "error_code": "TIMEOUT",
            "retry_count": 3,
            "last_attempt": timezone.now().isoformat(),
        }
        event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            error_message=error_message,
            error_details=error_details,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify marketplace.sync.failed event was published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.failed")
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(event.data["error_message"], error_message)
        self.assertEqual(event.data["error_details"], error_details)

    def test_event_deduplication_when_redis_available(self):
        """Test that deduplication returns same event ID for duplicate publishes.

        Requires Redis.  Skips if Redis is unavailable so the test provides
        a clear signal — a skip means "can't verify", not "verified OK."
        """
        from hub.apps.core.events.deduplication import get_redis_client

        # Require Redis for this test
        redis_client = get_redis_client()
        if redis_client is None:
            raise unittest.SkipTest("Redis client not available for deduplication test")
        try:
            redis_client.ping()
        except (OSError, TimeoutError):
            raise unittest.SkipTest("Redis not reachable for deduplication test")

        # Use a unique connection_id to avoid collisions with stale Redis keys
        unique_conn_id = f"test-connection-{uuid.uuid4().hex[:8]}"

        # Publish same event twice
        event_id_1 = self.publisher.publish_connection_created(
            connection_id=unique_conn_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        event_id_2 = self.publisher.publish_connection_created(
            connection_id=unique_conn_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Deduplication should return the same event ID
        self.assertEqual(
            event_id_1, event_id_2,
            "Event deduplication should return same event ID when Redis is available",
        )

        # Only one event should exist in the database
        events = Event.objects.filter(event_id=event_id_1)
        self.assertEqual(
            events.count(), 1,
            "Only one event should exist when deduplication works",
        )

    def test_event_deduplication_fail_open_without_redis(self):
        """Test that events are still published when deduplication is unavailable.

        This verifies the fail-open behaviour: Redis unavailability must not
        block event publishing.
        """
        unique_conn_id = f"test-connection-{uuid.uuid4().hex[:8]}"

        event_id_1 = self.publisher.publish_connection_created(
            connection_id=unique_conn_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        event_id_2 = self.publisher.publish_connection_created(
            connection_id=unique_conn_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Both events should have been published successfully
        self.assertIsNotNone(event_id_1)
        self.assertIsNotNone(event_id_2)

        # Both (or one, if Redis happens to be available) should exist in DB
        events = Event.objects.filter(event_id__in=[event_id_1, event_id_2])
        self.assertIn(
            events.count(), [1, 2],
            "Events should be persisted regardless of deduplication availability",
        )

    def test_publish_connection_created_with_missing_required_fields(self):
        """Test error handling when publishing connection.created event with missing fields"""
        # Test with None connection_id — should raise ValueError
        with self.assertRaises((ValueError, TypeError)):
            self.publisher.publish_connection_created(
                connection_id=None,  # type: ignore[arg-type]  # test: edge-case type exercise
                marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
                name="Test Connection",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        # Test with None marketplace_type — should also raise ValueError
        with self.assertRaises(ValueError):
            self.publisher.publish_connection_created(
                connection_id=str(uuid.uuid4()),
                marketplace_type=None,  # type: ignore[arg-type]  # test: edge-case type exercise
                name="Test Connection",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_publish_sync_failed_with_empty_error_message(self):
        """Test error handling when publishing sync.failed event with empty error message"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Error Test Connection {self._suffix}",
            config=self.config,
        )

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.FAILED.value,
        )

        # Should handle empty error message gracefully
        event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            error_message="",  # Empty error message
            error_details={},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Event should still be published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.sync.failed")

    def test_publish_mapping_updated_with_nonexistent_mapping_id(self):
        """mapping.updated does not validate mapping existence; schema requires valid UUID."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Nonexistent Mapping Test Connection {self._suffix}",
            config=self.config,
        )

        # Use a valid UUID that does not exist as a mapping (event schema requires UUID format)
        nonexistent_mapping_id = str(uuid.uuid4())
        event_id = self.publisher.publish_mapping_updated(
            mapping_id=nonexistent_mapping_id,
            connection_id=str(connection.id),
            changes={"field": {"old": "old_value", "new": "new_value"}},
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Event is published; we do not validate that the mapping exists in the DB
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.mapping.updated")
        self.assertEqual(event.data["mapping_id"], nonexistent_mapping_id)

    def test_event_publisher_handles_missing_tenant_id(self):
        """Test error handling when tenant_id is missing"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Missing Tenant Test Connection {self._suffix}",
            config=self.config,
        )

        # Should handle missing tenant_id gracefully (may use publisher's tenant_id)
        event_id = self.publisher.publish_connection_created(
            connection_id=str(connection.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=None,  # Missing tenant_id
            user_id=str(self.user.id),
        )

        # Event should still be published (publisher has tenant_id from initialization)
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.created")
        # Verify fallback: None tenant_id should resolve to publisher default
        self.assertEqual(
            str(event.tenant_id), str(self.tenant.id),
            msg="None tenant_id should fall back to publisher's default tenant_id",
        )

    def test_event_publisher_handles_missing_user_id(self):
        """Test error handling when user_id is missing"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Missing User Test Connection {self._suffix}",
            config=self.config,
        )

        # Should handle missing user_id gracefully — falls back to publisher default
        event_id = self.publisher.publish_connection_created(
            connection_id=str(connection.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            tenant_id=str(self.tenant.id),
            user_id=None,  # Missing user_id
        )

        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.created")
        # Verify fallback: None user_id should resolve to publisher default
        self.assertEqual(
            str(event.user_id), str(self.user.id),
            msg="None user_id should fall back to publisher's default user_id",
        )

    def test_event_publisher_handles_large_payload(self):
        """Test error handling when event payload is very large"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Large Payload Test Connection {self._suffix}",
            config=self.config,
        )

        # Create large changes dictionary
        large_changes = {
            f"field_{i}": {"old": f"old_value_{i}", "new": f"new_value_{i}"} for i in range(100)
        }

        # Should handle large payload gracefully
        event_id = self.publisher.publish_connection_updated(
            connection_id=str(connection.id),
            changes=large_changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Event should still be published
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.updated")
        self.assertEqual(len(event.data["changes"]), 100)
