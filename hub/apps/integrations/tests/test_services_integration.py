"""
Integration tests for MarketplaceIntegrationService.

Tests with real database and event publishing to verify:
- Event publishing works correctly
- Audit logging works correctly
- Distributed tracing works correctly
- Database transactions work correctly
"""
import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob, MarketplaceMapping
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus, DataMarketplaceConnector, MarketplaceListing, MarketplaceResource, MarketplaceAssetMapping, SyncResult
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.core.services.base import ValidationError, NotFoundError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core.events.models import Event
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.assets.models import AssetSourceType


pytestmark = pytest.mark.django_db(transaction=True)


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Use sync persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class MarketplaceIntegrationServiceIntegrationTest(TestCase):
    """Integration tests for MarketplaceIntegrationService with real database and events"""

    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
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

        # Register test connectors for integration tests
        # These are real connector implementations, not mocks
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
                    title="Test Listing"
                )

            def list_resources(self, listing_id: str):
                return []

            def create_listing(self, listing: MarketplaceListing):
                return listing

            def update_listing(self, listing_id: str, listing: MarketplaceListing):
                return listing

            def publish_resource(self, listing_id: str, resource: MarketplaceResource):
                return resource

            def download_resource(self, resource_id: str, destination_path: str):
                return destination_path

            def map_to_hub_asset(self, listing: MarketplaceListing):
                return MarketplaceAssetMapping(
                    asset_data={"name": "Test"},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                    odps_metadata={}
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test",
                    marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
                    title=asset_data.get("name", "Unknown")
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(status=SyncStatus.COMPLETED)

        class TestAWSConnector(TestSnowflakeConnector):
            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.AWS_DATA_EXCHANGE

        class TestDatabricksConnector(TestSnowflakeConnector):
            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.DATABRICKS_MARKETPLACE

        # Register connectors
        MarketplaceConnectorFactory.register_connector(MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestSnowflakeConnector)
        MarketplaceConnectorFactory.register_connector(MarketplaceType.AWS_DATA_EXCHANGE, TestAWSConnector)
        MarketplaceConnectorFactory.register_connector(MarketplaceType.DATABRICKS_MARKETPLACE, TestDatabricksConnector)

    def tearDown(self):
        """Clean up test connectors"""
        # Unregister test connectors
        try:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)
        except ValueError:
            pass
        try:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.AWS_DATA_EXCHANGE)
        except ValueError:
            pass
        try:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.DATABRICKS_MARKETPLACE)
        except ValueError:
            pass

    def test_create_connection_creates_audit_log(self):
        """Test that connection creation creates audit log"""
        # Count initial audit events
        initial_count = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION"
        ).count()

        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_CREATED",
            resource_id=str(connection.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertIn("connection_id", audit_event.details_json)
        self.assertEqual(
            audit_event.details_json["connection_id"],
            str(connection.id)
        )
        self.assertEqual(
            audit_event.details_json["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertEqual(
            audit_event.details_json["request_id"],
            "test-request-123"
        )

    def test_create_connection_publishes_event(self):
        """Test that connection creation publishes event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Verify event was published
        events = Event.objects.filter(
            event_type="integration.connection.created"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(
            event.data["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertEqual(event.data["name"], "Test Connection")
        self.assertIn("created_at", event.data)

    def test_update_connection_creates_audit_log(self):
        """Test that connection update creates audit log"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Update connection
        self.service.update_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Connection",
            is_active=False
        )

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_UPDATED",
            resource_id=str(connection.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertIn("changes", audit_event.details_json)
        self.assertIn("name", audit_event.details_json["changes"])
        self.assertIn("is_active", audit_event.details_json["changes"])

    def test_update_connection_publishes_event(self):
        """Test that connection update publishes event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Update connection
        self.service.update_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Connection"
        )

        # Verify event was published
        events = Event.objects.filter(
            event_type="integration.connection.updated"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertIn("changes", event.data)
        self.assertIn("updated_at", event.data)

    def test_delete_connection_creates_audit_log(self):
        """Test that connection deletion creates audit log"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )
        connection_id = str(connection.id)

        # Delete connection
        self.service.delete_connection(
            connection_id=connection_id,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="Test deletion"
        )

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_DELETED",
            resource_id=connection_id
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertEqual(
            audit_event.details_json["reason"],
            "Test deletion"
        )

    def test_delete_connection_publishes_event(self):
        """Test that connection deletion publishes event"""
        import time
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Delete connection
        self.service.delete_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Wait a moment for synchronous persistence to complete
        time.sleep(0.1)

        # Verify event was published
        events = Event.objects.filter(
            event_type="integration.connection.deleted"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(
            event.data["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertIn("deleted_at", event.data)

    def test_test_connection_creates_audit_log(self):
        """Test that connection testing creates audit log"""
        from unittest.mock import patch, MagicMock

        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Mock connector
        with patch('hub.apps.integrations.services.MarketplaceConnectorFactory') as mock_factory:
            mock_connector = MagicMock()
            mock_connector.test_connection.return_value = True
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_connector.return_value = mock_connector
            mock_factory.return_value = mock_factory_instance

            # Test connection
            self.service.test_connection(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Verify audit log was created
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_TESTED",
            resource_id=str(connection.id)
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertTrue(audit_event.details_json["success"])

    def test_test_connection_publishes_event(self):
        """Test that connection testing publishes event"""
        from unittest.mock import patch, MagicMock

        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Mock connector
        with patch('hub.apps.integrations.services.MarketplaceConnectorFactory') as mock_factory:
            mock_connector = MagicMock()
            mock_connector.test_connection.return_value = True
            mock_factory_instance = MagicMock()
            mock_factory_instance.create_connector.return_value = mock_connector
            mock_factory.return_value = mock_factory_instance

            # Test connection
            self.service.test_connection(
                connection_id=str(connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )

        # Verify event was published
        events = Event.objects.filter(
            event_type="integration.connection.tested"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertTrue(event.data["success"])
        self.assertIn("tested_at", event.data)

    def test_transaction_rollback_on_error(self):
        """Test that transaction rollback works on error"""
        # Try to create connection with invalid data
        with self.assertRaises(ValidationError):
            self.service.create_connection(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                marketplace_type="INVALID_TYPE",
                name="Test Connection",
                config=self.config
            )

        # Verify no connection was created
        connections = MarketplaceConnection.objects.filter(
            tenant_id=self.tenant.id,
            name="Test Connection"
        )
        self.assertEqual(connections.count(), 0)

        # Verify no audit log was created for failed operation
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_CREATED"
        )
        # Should have no events for this failed operation
        self.assertEqual(audit_events.count(), 0)

    def test_tenant_isolation(self):
        """Test that connections are isolated by tenant"""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2"
        )
        user2 = User.objects.create_user(
            email="test2@example.com",
            tenant=tenant2,
            status=UserStatus.ACTIVE
        )

        # Create connection for tenant 1
        connection1 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config=self.config
        )

        # Create connection for tenant 2
        service2 = MarketplaceIntegrationService(
            tenant_id=str(tenant2.id),
            user_id=str(user2.id)
        )
        connection2 = service2.create_connection(
            tenant_id=str(tenant2.id),
            user_id=str(user2.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",  # Same name, different tenant
            config=self.config
        )

        # Verify both connections exist
        self.assertNotEqual(connection1.id, connection2.id)

        # Verify tenant 1 can only see its own connections
        connections1 = self.service.list_connections(tenant_id=str(self.tenant.id))
        self.assertEqual(len(connections1), 1)
        self.assertEqual(connections1[0].id, connection1.id)

        # Verify tenant 2 can only see its own connections
        connections2 = service2.list_connections(tenant_id=str(tenant2.id))
        self.assertEqual(len(connections2), 1)
        self.assertEqual(connections2[0].id, connection2.id)

        # Verify tenant 1 cannot access tenant 2's connection
        with self.assertRaises(NotFoundError):
            self.service.get_connection(
                connection_id=str(connection2.id),
                tenant_id=str(self.tenant.id)
            )

    # --- sync_assets_to_marketplace integration tests ---
    def test_sync_assets_to_marketplace_creates_sync_job_and_job(self):
        """Test that sync_assets_to_marketplace creates sync job and background job."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Sync Test Connection",
            config=self.config
        )

        asset_ids = ["asset-1", "asset-2", "asset-3"]
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=asset_ids,
            options={"dry_run": False}
        )

        # Verify sync job was created
        self.assertIsNotNone(sync_job.id)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)
        self.assertEqual(sync_job.metadata['asset_ids'], asset_ids)

        # Verify background job was created
        self.assertIn('job_id', sync_job.metadata)
        job_id = sync_job.metadata['job_id']
        job = Job.objects.get(id=job_id)
        self.assertEqual(job.type, JobType.MARKETPLACE_SYNC)
        self.assertEqual(job.resource_type, "MARKETPLACE_SYNC_JOB")
        self.assertEqual(str(job.resource_id), str(sync_job.id))
        self.assertEqual(job.status, JobStatus.PENDING)

        # Verify audit log
        import time
        time.sleep(0.1)  # Allow for transaction commit
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_SYNC_JOB",
            action="SYNC_JOB_CREATED",
            resource_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.details_json['direction'], SyncDirection.PUSH.value)

        # Verify event was published
        time.sleep(0.1)  # Allow for event persistence
        event = Event.objects.filter(
            event_type="integration.sync_job.created",
            data__sync_job_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data['direction'], SyncDirection.PUSH.value)
        self.assertEqual(event.source_service, self.service.service_name)

    def test_sync_from_marketplace_creates_sync_job_and_job(self):
        """Test that sync_from_marketplace creates sync job and background job."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Pull Sync Test Connection",
            config=self.config
        )

        listing_ids = ["listing-1", "listing-2"]
        filters = {"category": "finance"}
        sync_job = self.service.sync_from_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=listing_ids,
            filters=filters,
            options={"create_assets": True}
        )

        # Verify sync job was created
        self.assertIsNotNone(sync_job.id)
        self.assertEqual(sync_job.direction, SyncDirection.PULL.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)
        self.assertEqual(sync_job.metadata['listing_ids'], listing_ids)
        self.assertEqual(sync_job.metadata['filters'], filters)

        # Verify background job was created
        self.assertIn('job_id', sync_job.metadata)
        job_id = sync_job.metadata['job_id']
        job = Job.objects.get(id=job_id)
        self.assertEqual(job.type, JobType.MARKETPLACE_SYNC)
        self.assertEqual(job.resource_type, "MARKETPLACE_SYNC_JOB")
        self.assertEqual(str(job.resource_id), str(sync_job.id))

        # Verify audit log
        import time
        time.sleep(0.1)
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_SYNC_JOB",
            action="SYNC_JOB_CREATED",
            resource_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.details_json['direction'], SyncDirection.PULL.value)

        # Verify event was published
        time.sleep(0.1)
        event = Event.objects.filter(
            event_type="integration.sync_job.created",
            data__sync_job_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data['direction'], SyncDirection.PULL.value)

    def test_get_sync_job_integration(self):
        """Test get_sync_job with real database."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Get Sync Job Test",
            config=self.config
        )

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        retrieved_job = self.service.get_sync_job(
            tenant_id=str(self.tenant.id),
            sync_job_id=str(sync_job.id)
        )

        self.assertEqual(retrieved_job.id, sync_job.id)
        self.assertEqual(retrieved_job.direction, SyncDirection.PUSH.value)

    def test_list_sync_jobs_integration(self):
        """Test list_sync_jobs with real database and filters."""
        connection1 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config=self.config
        )
        connection2 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Connection 2",
            config=self.config
        )

        sync_job1 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection1,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )
        sync_job2 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection2,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.RUNNING.value
        )
        sync_job3 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection1,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value
        )

        # List all sync jobs
        all_jobs = self.service.list_sync_jobs(tenant_id=str(self.tenant.id))
        self.assertEqual(len(all_jobs), 3)

        # Filter by connection
        connection1_jobs = self.service.list_sync_jobs(
            tenant_id=str(self.tenant.id),
            connection_id=str(connection1.id)
        )
        self.assertEqual(len(connection1_jobs), 2)
        self.assertIn(sync_job1, connection1_jobs)
        self.assertIn(sync_job3, connection1_jobs)

        # Filter by direction
        push_jobs = self.service.list_sync_jobs(
            tenant_id=str(self.tenant.id),
            direction=SyncDirection.PUSH.value
        )
        self.assertEqual(len(push_jobs), 2)
        self.assertIn(sync_job1, push_jobs)
        self.assertIn(sync_job3, push_jobs)

        # Filter by status
        pending_jobs = self.service.list_sync_jobs(
            tenant_id=str(self.tenant.id),
            status=SyncStatus.PENDING.value
        )
        self.assertEqual(len(pending_jobs), 1)
        self.assertEqual(pending_jobs[0].id, sync_job1.id)

    def test_cancel_sync_job_integration(self):
        """Test cancel_sync_job with real database and job cancellation."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Cancel Test Connection",
            config=self.config
        )

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        # Create background job
        from hub.apps.jobs.utils import create_job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.MARKETPLACE_SYNC,
            resource_type="MARKETPLACE_SYNC_JOB",
            resource_id=str(sync_job.id),
            details_json={'sync_job_id': str(sync_job.id)}
        )
        sync_job.metadata['job_id'] = str(job.id)
        sync_job.save(update_fields=['metadata', 'updated_at'])

        # Cancel sync job
        cancelled_job = self.service.cancel_sync_job(
            sync_job_id=str(sync_job.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="Integration test cancellation"
        )

        # Verify sync job was cancelled
        cancelled_job.refresh_from_db()
        self.assertEqual(cancelled_job.status, SyncStatus.FAILED.value)
        self.assertIsNotNone(cancelled_job.completed_at)
        self.assertTrue(len(cancelled_job.errors) > 0)
        self.assertIn("cancelled", cancelled_job.errors[0]['message'].lower())

        # Verify background job was cancelled
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.CANCELLED)

        # Verify audit log
        import time
        time.sleep(0.1)
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_SYNC_JOB",
            action="SYNC_JOB_CANCELLED",
            resource_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.details_json['reason'], "Integration test cancellation")

        # Verify event was published
        time.sleep(0.1)
        event = Event.objects.filter(
            event_type="integration.sync_job.cancelled",
            data__sync_job_id=str(sync_job.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data['reason'], "Integration test cancellation")

    def test_cancel_sync_job_terminal_state_validation(self):
        """Test that cancelling a terminal state sync job raises ValidationError."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Terminal State Test",
            config=self.config
        )

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value  # Terminal state
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.cancel_sync_job(
                sync_job_id=str(sync_job.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id)
            )
        self.assertIn("terminal state", str(cm.exception))

    def test_sync_job_tenant_isolation(self):
        """Test that sync jobs are isolated by tenant."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2"
        )
        user2 = User.objects.create_user(
            email="test2@example.com",
            tenant=tenant2,
            status=UserStatus.ACTIVE
        )

        connection1 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config=self.config
        )

        connection2 = MarketplaceConnection.objects.create(
            tenant=tenant2,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 2",
            config=self.config
        )

        sync_job1 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection1,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        sync_job2 = MarketplaceSyncJob.objects.create(
            tenant=tenant2,
            connection=connection2,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value
        )

        # Verify tenant 1 can only see its own sync jobs
        jobs1 = self.service.list_sync_jobs(tenant_id=str(self.tenant.id))
        self.assertEqual(len(jobs1), 1)
        self.assertEqual(jobs1[0].id, sync_job1.id)

        # Verify tenant 1 cannot access tenant 2's sync job
        with self.assertRaises(NotFoundError):
            self.service.get_sync_job(
                tenant_id=str(self.tenant.id),
                sync_job_id=str(sync_job2.id)
            )

    # --- create_mapping integration tests ---
    def test_create_mapping_creates_audit_log(self):
        """Test that mapping creation creates audit log."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Mapping Test Connection",
            config=self.config
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            description="Test asset"
        )

        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="listing-123",
            external_resource_ids=["resource-1"],
            sync_metadata={"test": "metadata"}
        )

        import time
        time.sleep(0.1)
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_MAPPING",
            action="MAPPING_CREATED",
            resource_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.details_json['external_listing_id'], "listing-123")

    def test_create_mapping_publishes_event(self):
        """Test that mapping creation publishes event."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Event Test Connection",
            config=self.config
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )

        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="listing-456"
        )

        import time
        time.sleep(0.1)
        event = Event.objects.filter(
            event_type="integration.mapping.created",
            data__mapping_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data['external_listing_id'], "listing-456")
        self.assertEqual(event.source_service, self.service.service_name)

    def test_get_mapping_integration(self):
        """Test get_mapping with real database."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Get Mapping Test",
            config=self.config
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )

        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="listing-789"
        )

        retrieved_mapping = self.service.get_mapping(
            mapping_id=str(mapping.id),
            tenant_id=str(self.tenant.id)
        )

        self.assertEqual(retrieved_mapping.id, mapping.id)
        self.assertEqual(retrieved_mapping.external_listing_id, "listing-789")

    def test_list_mappings_integration(self):
        """Test list_mappings with real database and filters."""
        connection1 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config=self.config
        )
        connection2 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,
            name="Connection 2",
            config=self.config
        )

        asset1 = Asset.objects.create(tenant=self.tenant, key="asset-1", name="Asset 1")
        asset2 = Asset.objects.create(tenant=self.tenant, key="asset-2", name="Asset 2")

        mapping1 = self.service.create_mapping(
            connection_id=str(connection1.id),
            hub_asset_id=str(asset1.id),
            external_listing_id="listing-1"
        )
        mapping2 = self.service.create_mapping(
            connection_id=str(connection2.id),
            hub_asset_id=str(asset2.id),
            external_listing_id="listing-2"
        )
        mapping3 = self.service.create_mapping(
            connection_id=str(connection1.id),
            hub_asset_id=str(asset2.id),
            external_listing_id="listing-3"
        )

        # List all mappings
        all_mappings = self.service.list_mappings(tenant_id=str(self.tenant.id))
        self.assertEqual(len(all_mappings), 3)

        # Filter by connection
        connection1_mappings = self.service.list_mappings(
            tenant_id=str(self.tenant.id),
            connection_id=str(connection1.id)
        )
        self.assertEqual(len(connection1_mappings), 2)
        self.assertIn(mapping1, connection1_mappings)
        self.assertIn(mapping3, connection1_mappings)

        # Filter by asset
        asset1_mappings = self.service.list_mappings(
            tenant_id=str(self.tenant.id),
            hub_asset_id=str(asset1.id)
        )
        self.assertEqual(len(asset1_mappings), 1)
        self.assertEqual(asset1_mappings[0].id, mapping1.id)

    def test_update_mapping_integration(self):
        """Test update_mapping with real database and event publishing."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Update Test Connection",
            config=self.config
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )

        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="listing-original",
            external_resource_ids=["resource-1"]
        )

        updated_mapping = self.service.update_mapping(
            mapping_id=str(mapping.id),
            external_listing_id="listing-updated",
            external_resource_ids=["resource-1", "resource-2"],
            sync_metadata={"last_sync": "2024-01-01"}
        )

        updated_mapping.refresh_from_db()
        self.assertEqual(updated_mapping.external_listing_id, "listing-updated")
        self.assertEqual(updated_mapping.external_resource_ids, ["resource-1", "resource-2"])
        self.assertEqual(updated_mapping.sync_metadata["last_sync"], "2024-01-01")

        # Verify audit log
        import time
        time.sleep(0.1)
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_MAPPING",
            action="MAPPING_UPDATED",
            resource_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertIn("external_listing_id", audit_event.details_json['changes'])

        # Verify event was published
        time.sleep(0.1)
        event = Event.objects.filter(
            event_type="integration.mapping.updated",
            data__mapping_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertIn("external_listing_id", event.data['changes'])

    def test_delete_mapping_integration(self):
        """Test delete_mapping with real database and event publishing."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Delete Test Connection",
            config=self.config
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset"
        )

        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="listing-to-delete"
        )

        self.service.delete_mapping(
            mapping_id=str(mapping.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="Integration test deletion"
        )

        # Verify mapping was deleted
        self.assertEqual(MarketplaceMapping.objects.filter(id=mapping.id).count(), 0)

        # Verify audit log
        import time
        time.sleep(0.1)
        audit_event = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_MAPPING",
            action="MAPPING_DELETED",
            resource_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.details_json['reason'], "Integration test deletion")

        # Verify event was published
        time.sleep(0.1)
        event = Event.objects.filter(
            event_type="integration.mapping.deleted",
            data__mapping_id=str(mapping.id)
        ).order_by('-timestamp').first()
        self.assertIsNotNone(event)
        self.assertEqual(event.data['reason'], "Integration test deletion")

    def test_mapping_tenant_isolation(self):
        """Test that mappings are isolated by tenant."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Test Tenant 2",
            slug="test-tenant-2"
        )
        user2 = User.objects.create_user(
            email="test2@example.com",
            tenant=tenant2,
            status=UserStatus.ACTIVE
        )

        connection1 = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 1",
            config=self.config
        )

        connection2 = MarketplaceConnection.objects.create(
            tenant=tenant2,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Connection 2",
            config=self.config
        )

        asset1 = Asset.objects.create(tenant=self.tenant, key="asset-1", name="Asset 1")
        asset2 = Asset.objects.create(tenant=tenant2, key="asset-2", name="Asset 2")

        mapping1 = self.service.create_mapping(
            connection_id=str(connection1.id),
            hub_asset_id=str(asset1.id),
            external_listing_id="listing-1"
        )

        mapping2 = MarketplaceMapping.objects.create(
            tenant=tenant2,
            connection=connection2,
            hub_asset=asset2,
            external_listing_id="listing-2"
        )

        # Verify tenant 1 can only see its own mappings
        mappings1 = self.service.list_mappings(tenant_id=str(self.tenant.id))
        self.assertEqual(len(mappings1), 1)
        self.assertEqual(mappings1[0].id, mapping1.id)

        # Verify tenant 1 cannot access tenant 2's mapping
        with self.assertRaises(NotFoundError):
            self.service.get_mapping(
                mapping_id=str(mapping2.id),
                tenant_id=str(self.tenant.id)
            )

    def test_create_connection_publishes_marketplace_event(self):
        """Test that connection creation publishes marketplace.connection.created event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.connection.created"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(
            event.data["marketplace_type"],
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertEqual(event.data["name"], "Test Connection")
        self.assertIn("created_at", event.data)

    def test_update_connection_publishes_marketplace_event(self):
        """Test that connection update publishes marketplace.connection.updated event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Update connection
        self.service.update_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Connection",
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.connection.updated"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertIn("changes", event.data)
        self.assertIn("updated_at", event.data)

    def test_delete_connection_publishes_marketplace_event(self):
        """Test that connection deletion publishes marketplace.connection.deleted event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Delete connection
        self.service.delete_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="Test deletion"
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.connection.deleted"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["name"], "Test Connection")
        self.assertEqual(event.data["reason"], "Test deletion")
        self.assertIn("deleted_at", event.data)

    def test_sync_from_marketplace_publishes_marketplace_sync_started_event(self):
        """Test that sync_from_marketplace publishes marketplace.sync.started event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Create sync job
        sync_job = self.service.sync_from_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=["listing-1", "listing-2"]
        )

        # Verify marketplace.sync.started event was published
        events = Event.objects.filter(
            event_type="marketplace.sync.started"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["direction"], SyncDirection.PULL.value)
        self.assertIn("started_at", event.data)

    def test_sync_assets_to_marketplace_publishes_marketplace_sync_started_event(self):
        """Test that sync_assets_to_marketplace publishes marketplace.sync.started event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED
        )

        # Create sync job
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)]
        )

        # Verify marketplace.sync.started event was published
        events = Event.objects.filter(
            event_type="marketplace.sync.started"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["sync_job_id"], str(sync_job.id))
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["direction"], SyncDirection.PUSH.value)
        self.assertIn("started_at", event.data)

    def test_create_mapping_publishes_marketplace_event(self):
        """Test that mapping creation publishes marketplace.mapping.created event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED
        )

        # Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.mapping.created"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["mapping_id"], str(mapping.id))
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["hub_asset_id"], str(asset.id))
        self.assertEqual(event.data["external_listing_id"], "ext-listing-123")
        self.assertIn("created_at", event.data)

    def test_update_mapping_publishes_marketplace_event(self):
        """Test that mapping update publishes marketplace.mapping.updated event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED
        )

        # Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Update mapping
        self.service.update_mapping(
            mapping_id=str(mapping.id),
            external_listing_id="ext-listing-456",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.mapping.updated"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["mapping_id"], str(mapping.id))
        self.assertIn("changes", event.data)
        self.assertIn("updated_at", event.data)

    def test_delete_mapping_publishes_marketplace_event(self):
        """Test that mapping deletion publishes marketplace.mapping.deleted event"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.FEDERATED
        )

        # Create mapping
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Delete mapping
        self.service.delete_mapping(
            mapping_id=str(mapping.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            reason="Test deletion"
        )

        # Verify marketplace event was published
        events = Event.objects.filter(
            event_type="marketplace.mapping.deleted"
        ).order_by('-timestamp')
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["mapping_id"], str(mapping.id))
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(event.data["hub_asset_id"], str(asset.id))
        self.assertEqual(event.data["external_listing_id"], "ext-listing-123")
        self.assertEqual(event.data["reason"], "Test deletion")
        self.assertIn("deleted_at", event.data)

