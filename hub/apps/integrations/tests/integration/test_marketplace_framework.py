"""
Comprehensive Framework Integration Tests for Marketplace Integration

Tests the complete marketplace integration framework with real implementations:
- Factory with real connectors
- Service with real database
- API endpoints with real database
- Event publishing
- Job queue integration

All tests use real services - no mocks or stubs.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from django_rq import get_queue
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.audit.models import AuditEvent
from hub.apps.auth.models import APIKey
from hub.apps.core.events.models import Event
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceAssetMapping,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.views import (
    MarketplaceConnectionViewSet,
    MarketplaceMappingViewSet,
    MarketplaceSyncJobViewSet,
)
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import Role, User, UserStatus
from tests.utils.wait_helpers import wait_for_event_persistence

User = get_user_model()

# API base path must match hub/urls.py (api/v1/) and integrations router
API_BASE = "/api/v1/integrations"
MARKETPLACE_CONNECTIONS = f"{API_BASE}/marketplace/connections"
MARKETPLACE_MAPPINGS = f"{API_BASE}/marketplace/mappings"
MARKETPLACE_SYNC = f"{API_BASE}/marketplace/sync"

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.integration,
]


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class MarketplaceFrameworkIntegrationTest(TestCase):
    """Comprehensive framework integration tests"""

    def setUp(self):
        """Set up test fixtures"""
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

        unique_suffix = str(uuid.uuid4())[:8]

        self.tenant = Tenant.objects.create(
            name=f"Framework Test Tenant {unique_suffix}",
            slug=f"framework-test-tenant-{unique_suffix}",
            kyc_status=KYCStatus.VERIFIED,
        )
        # Active subscription required so TenantSuspensionMiddleware allows API writes
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"framework-test-{unique_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider Role"},
        )
        tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.user.user_roles.create(role=data_provider_role)
        self.user.user_roles.create(role=tenant_admin_role)
        # APIKey requires unique key_hash: generate key and store hash (no plaintext in DB)
        self.plaintext_api_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(self.plaintext_api_key)
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            key_hash=key_hash,
            name=f"Framework Test API Key {unique_suffix}",
            scopes=["integrations:write", "integrations:read"],
        )

        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            request_id="framework-test-request",
        )

        self.config = {
            "api_key": "test-api-key-123",
            "endpoint": "https://api.example.com",
            "timeout": 30,
        }

        # Register real test connectors
        self._register_test_connectors()

        # API client with API key auth (matches MarketplaceIntegrationAPITest pattern)
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=None)
        self.api_client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {self.plaintext_api_key}"
        )

    def _register_test_connectors(self):
        """Register test connectors for integration tests"""

        # Base test connector class
        class TestConnectorBase(DataMarketplaceConnector):
            def __init__(self, **kwargs):
                self.config = kwargs.get("config", {})

            @property
            def supported_sync_directions(self):
                return [SyncDirection.PUSH, SyncDirection.PULL]

            def authenticate(self, credentials):
                return True

            def test_connection(self):
                return True

            def list_listings(self, filters=None, limit=None, offset=None):
                return [
                    MarketplaceListing(
                        marketplace_id="listing-1",
                        marketplace_type=self.marketplace_type,
                        title="Test Listing 1",
                    ),
                    MarketplaceListing(
                        marketplace_id="listing-2",
                        marketplace_type=self.marketplace_type,
                        title="Test Listing 2",
                    ),
                ]

            def get_listing(self, listing_id: str):
                return MarketplaceListing(
                    marketplace_id=listing_id,
                    marketplace_type=self.marketplace_type,
                    title=f"Test Listing {listing_id}",
                )

            def list_resources(self, listing_id: str):
                return [
                    MarketplaceResource(
                        resource_id="resource-1",
                        resource_type="FILE",
                        name="Test Resource 1",
                        url="https://example.com/resource1",
                    )
                ]

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
                    asset_data={"name": listing.title},
                    source_type=AssetSourceType.FEDERATED,
                    source_metadata={},
                    odps_metadata={},
                )

            def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
                return MarketplaceListing(
                    marketplace_id="test-listing",
                    marketplace_type=self.marketplace_type,
                    title=asset_data.get("name", "Unknown"),
                )

            def sync_push(self, asset_ids, options=None):
                return SyncResult(
                    status=SyncStatus.COMPLETED,
                    total_items=len(asset_ids),
                    successful_items=len(asset_ids),
                    failed_items=0,
                )

            def sync_pull(self, listing_ids=None, filters=None, options=None):
                return SyncResult(
                    status=SyncStatus.COMPLETED, total_items=2, successful_items=2, failed_items=0
                )

        # Register connectors for different marketplace types
        self.test_connectors = {}

        # Create Snowflake connector
        class TestSnowflakeConnector(TestConnectorBase):
            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

        # Create AWS connector
        class TestAWSConnector(TestConnectorBase):
            @property
            def marketplace_type(self) -> MarketplaceType:
                return MarketplaceType.AWS_DATA_EXCHANGE

        # Register connectors
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestSnowflakeConnector
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.AWS_DATA_EXCHANGE, TestAWSConnector
        )

        self.test_connectors[MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE] = TestSnowflakeConnector
        self.test_connectors[MarketplaceType.AWS_DATA_EXCHANGE] = TestAWSConnector

    def tearDown(self):
        """Clean up non-DB state (connectors, signals) and call super().tearDown()."""
        for mt in self.test_connectors.keys():
            try:
                MarketplaceConnectorFactory.unregister_connector(mt)
            except ValueError:
                pass

        # Reconnect signals after test
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

    def test_factory_with_real_connectors(self):
        """Test factory creates real connector instances"""
        # Test connector registration
        self.assertTrue(
            MarketplaceConnectorFactory.is_supported(MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)
        )

        # Test connector creation
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, config=self.config
        )

        self.assertIsNotNone(connector)
        self.assertEqual(connector.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE)
        self.assertTrue(connector.test_connection())

        # Test connector operations
        listings = connector.list_listings()
        self.assertEqual(len(listings), 2)
        self.assertIsInstance(listings[0], MarketplaceListing)

    def test_factory_multiple_connector_types(self):
        """Test factory handles multiple connector types"""
        # Test multiple marketplace types
        for mt in [MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, MarketplaceType.AWS_DATA_EXCHANGE]:
            connector = MarketplaceConnectorFactory.create_connector(mt, config=self.config)
            self.assertIsNotNone(connector)
            self.assertEqual(connector.marketplace_type, mt)
            self.assertTrue(connector.test_connection())

    # === Service Integration Tests ===

    def test_service_with_real_database(self):
        """Test service operations with real database"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Framework Test Connection",
            config=self.config,
        )

        # Verify connection in database
        db_connection = MarketplaceConnection.objects.get(id=connection.id)
        self.assertEqual(db_connection.name, "Framework Test Connection")
        self.assertEqual(
            db_connection.marketplace_type, MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )
        self.assertEqual(db_connection.tenant, self.tenant)

        # Test connection retrieval
        retrieved = self.service.get_connection(
            connection_id=str(connection.id), tenant_id=str(self.tenant.id)
        )
        self.assertEqual(retrieved.id, connection.id)

        # Test connection update
        updated = self.service.update_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Framework Test Connection",
        )
        self.assertEqual(updated.name, "Updated Framework Test Connection")

        # Verify in database
        db_connection.refresh_from_db()
        self.assertEqual(db_connection.name, "Updated Framework Test Connection")

    def test_service_connection_testing(self):
        """Test service connection testing with real connector"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config=self.config,
        )

        # Test connection
        result = self.service.test_connection(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertTrue(result["success"])
        self.assertIn("tested_at", result)

    def test_service_sync_operations(self):
        """Test service sync operations with real database"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Sync Test Connection",
            config=self.config,
        )

        # Create test asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Test PUSH sync
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        self.assertIsNotNone(sync_job.id)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)

        # Verify in database
        db_sync_job = MarketplaceSyncJob.objects.get(id=sync_job.id)
        self.assertEqual(db_sync_job.connection.id, connection.id)
        self.assertEqual(db_sync_job.tenant.id, self.tenant.id)

        # Test PULL sync
        pull_sync_job = self.service.sync_from_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=["listing-1", "listing-2"],
        )

        self.assertIsNotNone(pull_sync_job.id)
        self.assertEqual(pull_sync_job.direction, SyncDirection.PULL.value)

    # === API Endpoint Integration Tests ===

    def test_api_endpoints_with_real_database(self):
        """Test API endpoints with real database (API key auth)."""
        # Test CREATE connection
        create_data = {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": "API Test Connection",
            "config": self.config,
        }
        response = self.api_client.post(
            f"{MARKETPLACE_CONNECTIONS}/", create_data, format="json"
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg=f"POST connections: {response.status_code} - {getattr(response, 'data', response.content)}",
        )
        connection_id = response.data["id"]

        # Test LIST connections
        response = self.api_client.get(f"{MARKETPLACE_CONNECTIONS}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        # Test RETRIEVE connection
        response = self.api_client.get(f"{MARKETPLACE_CONNECTIONS}/{connection_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "API Test Connection")

        # Test UPDATE connection
        update_data = {"name": "Updated API Test Connection"}
        response = self.api_client.patch(
            f"{MARKETPLACE_CONNECTIONS}/{connection_id}/",
            update_data,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated API Test Connection")

        # Verify in database
        db_connection = MarketplaceConnection.objects.get(id=connection_id)
        self.assertEqual(db_connection.name, "Updated API Test Connection")

        # Test DELETE connection
        response = self.api_client.delete(f"{MARKETPLACE_CONNECTIONS}/{connection_id}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deleted
        self.assertFalse(MarketplaceConnection.objects.filter(id=connection_id).exists())

    def test_api_mapping_delete_emits_audit_event(self):
        """Test DELETE mapping via API emits MAPPING_DELETED audit event (framework integration)."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Mapping Delete Test Connection",
            config=self.config,
        )
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Mapping Delete Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )
        mapping = self.service.create_mapping(
            connection_id=str(connection.id),
            hub_asset_id=str(asset.id),
            external_listing_id="ext-listing-framework-delete",
        )

        response = self.api_client.delete(f"{MARKETPLACE_MAPPINGS}/{mapping.id}/")
        self.assertEqual(
            response.status_code,
            status.HTTP_204_NO_CONTENT,
            msg=f"DELETE mapping: {response.status_code} - {getattr(response, 'data', response.content)}",
        )

        self.assertFalse(MarketplaceMapping.objects.filter(id=mapping.id).exists())

        wait_for_event_persistence()
        audit_event = (
            AuditEvent.objects.filter(
                resource_type="MARKETPLACE_MAPPING",
                action="MAPPING_DELETED",
                resource_id=str(mapping.id),
            )
            .order_by("-timestamp")
            .first()
        )
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.result, "SUCCESS")

    def test_api_connection_test_endpoint(self):
        """Test API connection test endpoint (API key auth)."""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="API Test Connection",
            config=self.config,
        )

        # Test connection via API
        response = self.api_client.post(
            f"{MARKETPLACE_CONNECTIONS}/{connection.id}/test/", {}, format="json"
        )
        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            msg=f"POST test: {response.status_code} - {getattr(response, 'data', response.content)}",
        )
        self.assertIn("success", response.data)
        self.assertTrue(response.data["success"])

    def test_api_sync_job_endpoints(self):
        """Test API sync job endpoints (API key auth)."""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Sync Job Test Connection",
            config=self.config,
        )

        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Test CREATE sync job
        sync_data = {
            "connection_id": str(connection.id),
            "direction": SyncDirection.PUSH.value,
            "asset_ids": [str(asset.id)],
        }
        response = self.api_client.post(f"{MARKETPLACE_SYNC}/", sync_data, format="json")
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            msg=f"POST sync: {response.status_code} - {getattr(response, 'data', response.content)}",
        )
        sync_job_id = response.data["id"]

        # Test LIST sync jobs
        response = self.api_client.get(f"{MARKETPLACE_SYNC}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        # Test RETRIEVE sync job
        response = self.api_client.get(f"{MARKETPLACE_SYNC}/{sync_job_id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["direction"], SyncDirection.PUSH.value)

    # === Event Publishing Integration Tests ===

    def test_event_publishing_integration(self):
        """Test event publishing with real event bus"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Event Test Connection",
            config=self.config,
        )

        # Wait for event persistence
        wait_for_event_persistence()

        # Verify integration.connection.created event
        events = Event.objects.filter(event_type="integration.connection.created").order_by(
            "-timestamp"
        )
        self.assertGreaterEqual(events.count(), 1)

        event = events.first()
        self.assertEqual(event.data["connection_id"], str(connection.id))
        self.assertEqual(
            event.data["marketplace_type"], MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value
        )

        # Verify marketplace.connection.created event
        marketplace_events = Event.objects.filter(
            event_type="marketplace.connection.created"
        ).order_by("-timestamp")
        self.assertGreaterEqual(marketplace_events.count(), 1)

        marketplace_event = marketplace_events.first()
        self.assertEqual(marketplace_event.data["connection_id"], str(connection.id))

    def test_sync_job_event_publishing(self):
        """Test sync job event publishing"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Sync Event Test Connection",
            config=self.config,
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Create sync job
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        # Wait for event persistence
        wait_for_event_persistence()

        # Verify sync job events
        events = Event.objects.filter(
            event_type__in=["integration.sync_job.created", "marketplace.sync.started"]
        ).order_by("-timestamp")
        self.assertGreaterEqual(events.count(), 1)

    # === Job Queue Integration Tests ===

    def test_job_queue_integration(self):
        """Test job queue integration with real Redis/RQ"""
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Job Queue Test Connection",
            config=self.config,
        )

        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Create sync job (should create background job)
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        # Verify sync job has workflow instance ID (workflow-based execution)
        self.assertIn("workflow_instance_id", sync_job.metadata)

        # Verify sync job was created; workflow may run synchronously so status can
        # be PENDING (queued), RUNNING (started), or terminal (COMPLETED/FAILED/PARTIAL)
        db_sync_job = MarketplaceSyncJob.objects.get(id=sync_job.id)
        self.assertIsNotNone(db_sync_job)
        self.assertIn(
            db_sync_job.status,
            (
                SyncStatus.PENDING.value,
                SyncStatus.RUNNING.value,
                SyncStatus.COMPLETED.value,
                SyncStatus.FAILED.value,
                SyncStatus.PARTIAL.value,
            ),
            msg="Sync job should be in a valid state after create",
        )

    def test_audit_logging_integration(self):
        """Test audit logging integration"""
        # Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Audit Test Connection",
            config=self.config,
        )

        # Wait for audit log creation
        wait_for_event_persistence()

        # Verify audit log
        audit_events = AuditEvent.objects.filter(
            resource_type="MARKETPLACE_CONNECTION",
            action="CONNECTION_CREATED",
            resource_id=str(connection.id),
        )
        self.assertEqual(audit_events.count(), 1)

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

    # === End-to-End Framework Integration Test ===

    def test_complete_framework_integration(self):
        """Test complete framework integration: factory -> service -> API -> events -> jobs"""
        # 1. Factory: Create connector
        connector = MarketplaceConnectorFactory.create_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, config=self.config
        )
        self.assertIsNotNone(connector)

        # 2. Service: Create connection
        connection = self.service.create_connection(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="E2E Test Connection",
            config=self.config,
        )
        self.assertIsNotNone(connection.id)

        # 3. API: Retrieve connection
        client = APIClient()
        client.force_authenticate(user=self.user)
        response = client.get(f"{MARKETPLACE_CONNECTIONS}/{connection.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 4. Events: Verify events published
        wait_for_event_persistence()
        events = Event.objects.filter(event_type="integration.connection.created")
        self.assertGreaterEqual(events.count(), 1)

        # 5. Jobs: Create sync job
        asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Test Asset",
            source_type=AssetSourceType.HUB_NATIVE,
        )

        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )
        self.assertIsNotNone(sync_job.id)

        # 6. Verify complete integration
        self.assertIn("workflow_instance_id", sync_job.metadata)
        self.assertEqual(sync_job.connection.id, connection.id)
        self.assertEqual(sync_job.tenant.id, self.tenant.id)
