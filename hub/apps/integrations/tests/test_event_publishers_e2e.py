"""
End-to-end tests for MarketplaceEventPublisher.

Tests complete workflows with event publishing, verifying end-to-end behavior
across multiple operations and event types.
"""

import uuid

from django.db import connection, connections
from django.db.utils import InterfaceError as DjangoInterfaceError
from django.db.utils import OperationalError
from django.test import TransactionTestCase, override_settings

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


def _is_connection_closed_error(exc: BaseException) -> bool:
    """True if the exception indicates the DB connection was closed (any backend or wrapper)."""
    msg = str(exc).lower()
    return "connection" in msg and "closed" in msg


def _ensure_db_connection():
    """Ensure default DB connection is open so setUp never see 'connection already closed'."""
    try:
        connections.close_all()
        connection.ensure_connection()
    except (DjangoInterfaceError, OperationalError):
        pass


def _ensure_db_connection_for_teardown():
    """Ensure connection for tearDown/flush without closing first (avoid breaking active connection)."""
    try:
        connection.ensure_connection()
    except (DjangoInterfaceError, OperationalError):
        try:
            connections.close_all()
            connection.ensure_connection()
        except (DjangoInterfaceError, OperationalError):
            pass


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceEventPublisherE2ETest(TransactionTestCase):
    """
    E2E tests for MarketplaceEventPublisher workflows.

    Uses TransactionTestCase; _fixture_teardown skipped to avoid slow
    TRUNCATE CASCADE that causes timeouts in batched runs.
    """

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""

    def setUp(self):
        """Set up test fixtures; retry once on connection closed."""
        _ensure_db_connection()
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

        last_error = None
        for _ in range(3):
            try:
                self._create_fixtures()
                last_error = None
                break
            except (DjangoInterfaceError, OperationalError) as e:
                last_error = e
                if _is_connection_closed_error(e):
                    _ensure_db_connection()
                    continue
                raise
        if last_error is not None:
            raise last_error

    def _create_fixtures(self):
        """Create tenant, user, publisher, service, and config. Unique slug per run to avoid collisions."""
        slug_suffix = uuid.uuid4().hex[:8]
        self._suffix = slug_suffix
        self.tenant = Tenant.objects.create(
            name=f"E2E Test Tenant {slug_suffix}",
            slug=f"e2e-test-tenant-{slug_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"e2e-{slug_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.publisher = MarketplaceEventPublisher(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="e2e-test-request"
        )
        self.config = {
            "api_key": "e2e-api-key",
            "endpoint": "https://api.example.com",
            "timeout": 30,
        }

    def tearDown(self):
        """Reconnect signals after test."""
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass

    def test_complete_connection_lifecycle_manual_publishing(self):
        """Test complete connection lifecycle with all event types."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"E2E Connection {self._suffix}",
            config=self.config,
        )

        # Verify connection.created event (from service)
        created_events = Event.objects.filter(
            event_type="integration.connection.created", data__connection_id=str(connection.id)
        )
        self.assertGreaterEqual(created_events.count(), 1)

        # Publish marketplace.connection.created event
        event_id = self.publisher.publish_connection_created(
            connection_id=str(connection.id),
            marketplace_type=connection.marketplace_type,
            name=connection.name,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)

        # Update connection
        old_name = connection.name
        connection.name = f"Updated E2E Connection {self._suffix}"
        connection.is_active = False
        connection.save()

        # Publish marketplace.connection.updated event
        changes = {
            "name": {"old": old_name, "new": connection.name},
            "is_active": {"old": True, "new": False},
        }
        event_id = self.publisher.publish_connection_updated(
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)

        # Verify marketplace.connection.updated event
        updated_event = Event.objects.get(event_id=event_id)
        self.assertEqual(updated_event.event_type, "marketplace.connection.updated")
        self.assertEqual(updated_event.data["changes"], changes)

        # Delete connection
        connection.delete()

        # Publish marketplace.connection.deleted event
        event_id = self.publisher.publish_connection_deleted(
            connection_id=str(connection.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=connection.name,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)

        # Verify marketplace.connection.deleted event
        deleted_event = Event.objects.get(event_id=event_id)
        self.assertEqual(deleted_event.event_type, "marketplace.connection.deleted")

    def test_complete_sync_workflow_manual_publishing(self):
        """Test complete sync workflow with all sync event types."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Sync E2E Connection {self._suffix}",
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
        started_event_id = self.publisher.publish_sync_started(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(started_event_id)

        # Verify marketplace.sync.started event
        started_event = Event.objects.get(event_id=started_event_id)
        self.assertEqual(started_event.event_type, "marketplace.sync.started")

        # Simulate sync completion
        sync_job.status = SyncStatus.COMPLETED.value
        sync_job.save()

        # Publish sync.completed event
        completed_event_id = self.publisher.publish_sync_completed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            status=SyncStatus.COMPLETED.value,
            items_synced=25,
            items_failed=0,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(completed_event_id)

        # Verify marketplace.sync.completed event
        completed_event = Event.objects.get(event_id=completed_event_id)
        self.assertEqual(completed_event.event_type, "marketplace.sync.completed")
        self.assertEqual(completed_event.data["items_synced"], 25)
        self.assertEqual(completed_event.data["items_failed"], 0)

    def test_complete_sync_failure_manual_publishing(self):
        """Test complete sync failure workflow."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Failed Sync E2E Conn {self._suffix}",
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
        started_event_id = self.publisher.publish_sync_started(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(started_event_id)

        # Simulate sync failure
        sync_job.status = SyncStatus.FAILED.value
        sync_job.save()

        # Publish sync.failed event
        failed_event_id = self.publisher.publish_sync_failed(
            sync_job_id=str(sync_job.id),
            connection_id=str(connection.id),
            direction=sync_job.direction,
            error_message="Network timeout",
            error_details={
                "error_code": "NETWORK_TIMEOUT",
                "retry_count": 3,
                "last_error": "Connection refused",
            },
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(failed_event_id)

        # Verify marketplace.sync.failed event
        failed_event = Event.objects.get(event_id=failed_event_id)
        self.assertEqual(failed_event.event_type, "marketplace.sync.failed")
        self.assertEqual(failed_event.data["error_message"], "Network timeout")

    def test_complete_mapping_lifecycle_manual_publishing(self):
        """Test complete mapping lifecycle with all mapping event types."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Mapping E2E Conn {self._suffix}",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"E2E Test Asset {self._suffix}",
            source_type="FEDERATED",
        )

        # Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="e2e-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify integration.mapping.created event (from service)
        created_events = Event.objects.filter(
            event_type="integration.mapping.created", data__mapping_id=str(mapping.id)
        )
        self.assertGreaterEqual(created_events.count(), 1)

        # Publish marketplace.mapping.created event
        created_event_id = self.publisher.publish_mapping_created(
            mapping_id=str(mapping.id),
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id=mapping.external_listing_id,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(created_event_id)

        # Update mapping
        mapping.external_listing_id = "e2e-listing-456"
        mapping.save()

        # Publish marketplace.mapping.updated event
        changes = {"external_listing_id": {"old": "e2e-listing-123", "new": "e2e-listing-456"}}
        updated_event_id = self.publisher.publish_mapping_updated(
            mapping_id=str(mapping.id),
            connection_id=str(connection.id),
            changes=changes,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(updated_event_id)

        # Verify marketplace.mapping.updated event
        updated_event = Event.objects.get(event_id=updated_event_id)
        self.assertEqual(updated_event.event_type, "marketplace.mapping.updated")
        self.assertEqual(updated_event.data["changes"], changes)

        # Delete mapping
        mapping_id = str(mapping.id)
        mapping.delete()

        # Publish marketplace.mapping.deleted event
        deleted_event_id = self.publisher.publish_mapping_deleted(
            mapping_id=mapping_id,
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="e2e-listing-456",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(deleted_event_id)

        # Verify marketplace.mapping.deleted event
        deleted_event = Event.objects.get(event_id=deleted_event_id)
        self.assertEqual(deleted_event.event_type, "marketplace.mapping.deleted")

    def test_multiple_event_types_in_sequence(self):
        """Test publishing multiple different event types in sequence."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Multi Event Conn {self._suffix}",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Multi Event Asset {self._suffix}",
            source_type="FEDERATED",
        )

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
        )

        # Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="multi-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Publish all event types in sequence
        event_ids = []

        # Connection events
        event_ids.append(
            self.publisher.publish_connection_created(
                connection_id=str(connection.id),
                marketplace_type=connection.marketplace_type,
                name=connection.name,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
        )

        # Sync events
        event_ids.append(
            self.publisher.publish_sync_started(
                sync_job_id=str(sync_job.id),
                connection_id=str(connection.id),
                direction=sync_job.direction,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
        )

        # Mapping events
        event_ids.append(
            self.publisher.publish_mapping_created(
                mapping_id=str(mapping.id),
                connection_id=str(connection.id),
                hub_asset_id=str(asset.id),
                external_listing_id=mapping.external_listing_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
        )

        # Verify all events were published
        for event_id in event_ids:
            self.assertIsNotNone(event_id)
            event = Event.objects.get(event_id=event_id)
            self.assertIsNotNone(event)

        # Verify event types
        events = Event.objects.filter(event_id__in=event_ids)
        event_types = {e.event_type for e in events}
        self.assertIn("marketplace.connection.created", event_types)
        self.assertIn("marketplace.sync.started", event_types)
        self.assertIn("marketplace.mapping.created", event_types)

    def test_event_publishing_with_invalid_connection_id(self):
        """Test event publishing with non-existent connection ID.

        Event publishing does NOT validate connection existence — it's
        a fire-and-forget notification, not a domain gate.
        """
        fake_connection_id = "00000000-0000-0000-0000-000000000000"
        event_id = self.publisher.publish_connection_created(
            connection_id=fake_connection_id,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Fake Connection",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)

    def test_event_publishing_with_empty_event_data(self):
        """Test event publishing with empty name field.

        Event publishing does NOT enforce business-level validation on
        field values — it's a fire-and-forget notification layer.
        """
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=f"Empty Data Conn {self._suffix}",
            config=self.config,
        )

        event_id = self.publisher.publish_connection_created(
            connection_id=str(connection.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="",  # Empty name — publisher doesn't enforce business validation
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)

    def test_event_publishing_with_none_tenant_id(self):
        """Test event publishing error handling with None tenant ID"""
        conn_name = f"None Tenant Conn {self._suffix}"
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=conn_name,
            config=self.config,
        )

        # Publisher allows None tenant_id — it should fall back to the
        # publisher's default tenant_id (set during __init__).
        event_id = self.publisher.publish_connection_created(
            connection_id=str(connection.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name=conn_name,
            tenant_id=None,
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "marketplace.connection.created")
        # Verify fallback: None tenant_id should resolve to publisher default
        self.assertEqual(
            str(event.tenant_id), str(self.tenant.id),
            msg="None tenant_id should fall back to publisher's default tenant_id",
        )

    def test_event_publishing_with_invalid_sync_job_id(self):
        """Test event publishing with non-existent sync job ID.

        Event publishing does NOT validate sync job existence — it's
        a fire-and-forget notification, not a domain gate.
        """
        fake_sync_job_id = "00000000-0000-0000-0000-000000000000"
        event_id = self.publisher.publish_sync_started(
            sync_job_id=fake_sync_job_id,
            connection_id="test-connection-id",
            direction=SyncDirection.PULL.value,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsNotNone(event_id)
