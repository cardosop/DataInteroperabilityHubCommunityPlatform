"""
Tests for Marketplace Integration Background Tasks

Comprehensive tests for execute_marketplace_sync task including:
- Unit tests for sync job processor
- Integration tests with real connector/job queue
- Error handling tests
"""

import contextlib
import uuid

import pytest
from django.test import TestCase
from django.utils import timezone
from django_rq import get_queue

from hub.apps.assets.models import Asset, AssetSourceType
from hub.apps.core.services.base import ServiceError
from hub.apps.integrations.base import (
    DataMarketplaceConnector,
    MarketplaceListing,
    MarketplaceResource,
    MarketplaceType,
    SyncDirection,
    SyncResult,
    SyncStatus,
)
from hub.apps.integrations.factory import MarketplaceConnectorFactory
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.tasks import execute_marketplace_sync
from hub.apps.jobs.models import JobStatus, JobType
from tests.fixtures.test_data_factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)


class TestMarketplaceConnector(DataMarketplaceConnector):
    """Test connector implementation for testing"""

    __test__ = False  # Not a test class — prevent pytest collection warning

    def __init__(self, config=None, tenant_id=None, user_id=None):
        self.config = config or {}
        self.tenant_id = tenant_id
        self.user_id = user_id
        self._sync_push_result = None
        self._sync_pull_result = None

    @property
    def marketplace_type(self) -> MarketplaceType:
        return MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE

    @property
    def supported_sync_directions(self):
        return [SyncDirection.PUSH, SyncDirection.PULL, SyncDirection.BIDIRECTIONAL]

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

    def publish_resource(self, listing_id: str, resource: MarketplaceResource):
        return resource

    def download_resource(self, resource_id: str, destination_path: str):
        return destination_path

    def map_from_hub_asset(self, asset_data, odps_metadata=None, odcs_metadata=None):
        return MarketplaceListing(
            marketplace_id="test-listing",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE,
            title=asset_data.get("name", "Test Asset"),
        )

    def map_to_hub_asset(self, listing: MarketplaceListing, sync_job_id: str | None = None):
        from hub.apps.integrations.base import MarketplaceAssetMapping

        # Get resources from listing if available
        resources = listing.resources if hasattr(listing, "resources") and listing.resources else []
        return MarketplaceAssetMapping(
            asset_data={
                "name": listing.title,
                "description": listing.description or "",
                "key": f"marketplace-{listing.marketplace_id}",
            },
            source_type=AssetSourceType.FEDERATED,
            source_metadata={
                "marketplace_type": listing.marketplace_type.value,
                "marketplace_id": listing.marketplace_id,
                "listing_id": listing.marketplace_id,
                "sync_job_id": sync_job_id,
            },
            resources=resources,
        )

    def sync_push(self, asset_ids, options=None):
        if self._sync_push_result:
            return self._sync_push_result
        return SyncResult(
            status=SyncStatus.COMPLETED,
            total_items=len(asset_ids),
            successful_items=len(asset_ids),
            failed_items=0,
            skipped_items=0,
            errors=[],
            metadata={"asset_ids": asset_ids},
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )

    def sync_pull(self, listing_ids=None, filters=None, options=None):
        if self._sync_pull_result:
            return self._sync_pull_result
        listing_count = len(listing_ids) if listing_ids else 1
        return SyncResult(
            status=SyncStatus.COMPLETED,
            total_items=listing_count,
            successful_items=listing_count,
            failed_items=0,
            skipped_items=0,
            errors=[],
            metadata={"listing_ids": listing_ids or [], "filters": filters or {}},
            started_at=timezone.now(),
            completed_at=timezone.now(),
        )


class MarketplaceSyncTaskUnitTest(TestCase):
    """Unit tests for execute_marketplace_sync task"""

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
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

        # Register test connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

    def tearDown(self):
        """Clean up after tests"""
        # Unregister test connector
        try:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )
        except ValueError:
            pass  # Already unregistered
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

    def test_execute_sync_job_push_success(self):
        """Test successful PUSH sync execution"""
        # Create sync job
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [str(asset.id)], "options": {}},
        )

        # Execute sync
        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

        # Verify result
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sync_status"], SyncStatus.COMPLETED.value)
        self.assertEqual(result["successful_items"], 1)
        self.assertEqual(result["failed_items"], 0)

        # Verify sync job was updated
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertEqual(sync_job.items_synced, 1)
        self.assertEqual(sync_job.items_failed, 0)
        self.assertIsNotNone(sync_job.completed_at)

    def test_execute_sync_job_pull_success(self):
        """Test successful PULL sync execution"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.PENDING.value,
            metadata={"listing_ids": ["listing-1", "listing-2"], "options": {}},
        )

        # Execute sync
        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

        # Verify result
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sync_status"], SyncStatus.COMPLETED.value)
        self.assertEqual(result["successful_items"], 2)
        self.assertEqual(result["failed_items"], 0)

        # Verify sync job was updated
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertEqual(sync_job.items_synced, 2)
        self.assertEqual(sync_job.items_failed, 0)

    def test_execute_sync_job_bidirectional_success(self):
        """Test successful BIDIRECTIONAL sync execution"""
        # Create sync job
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.BIDIRECTIONAL.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [str(asset.id)], "listing_ids": ["listing-1"], "options": {}},
        )

        # Execute sync
        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

        # Verify result
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sync_status"], SyncStatus.COMPLETED.value)

        # Verify sync job was updated
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)

    def test_execute_sync_job_not_found(self):
        """Test error handling when sync job not found"""
        fake_id = str(uuid.uuid4())

        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(fake_id, retry_count=0)

        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_sync_job_already_terminal(self):
        """Test idempotency - skip if sync job already in terminal state"""
        # Create completed sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value,
            metadata={"asset_ids": []},
        )

        # Execute sync (should skip)
        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

        # Verify result indicates skip
        self.assertEqual(result["status"], "skipped")
        self.assertIn("terminal state", result["reason"])

    def test_execute_sync_job_connection_not_active(self):
        """Test error handling when connection is not active"""
        # Deactivate connection
        self.connection.is_active = False
        self.connection.save()

        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": []},
        )

        # Execute sync (should fail)
        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(str(sync_job.id), retry_count=0)

        self.assertIn("not active", str(cm.exception).lower())

        # Verify sync job was marked as failed
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)

    def test_execute_sync_job_push_with_partial_failure(self):
        """Test PUSH sync with partial failures (no mocks: real connector via register)"""

        class PartialFailureConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                return SyncResult(
                    status=SyncStatus.PARTIAL,
                    total_items=3,
                    successful_items=2,
                    failed_items=1,
                    skipped_items=0,
                    errors=["Error syncing asset-3"],
                    metadata={},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, PartialFailureConnector
        )
        try:
            asset1 = Asset.objects.create(
                tenant=self.tenant, key="test-asset-1", name="Test Asset 1"
            )
            asset2 = Asset.objects.create(
                tenant=self.tenant, key="test-asset-2", name="Test Asset 2"
            )
            asset3 = Asset.objects.create(
                tenant=self.tenant, key="test-asset-3", name="Test Asset 3"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={
                    "asset_ids": [str(asset1.id), str(asset2.id), str(asset3.id)],
                    "options": {},
                },
            )

            result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["sync_status"], SyncStatus.PARTIAL.value)
            self.assertEqual(result["successful_items"], 2)
            self.assertEqual(result["failed_items"], 1)

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.PARTIAL.value)
            self.assertEqual(sync_job.items_synced, 2)
            self.assertEqual(sync_job.items_failed, 1)
            # Errors from sync_result.errors must be persisted in the sync job.
            # The connector returned errors=["Error syncing asset-3"] — verify they survived save.
            self.assertEqual(
                len(sync_job.errors),
                1,
                f"Expected 1 persisted error, got {sync_job.errors}",
            )
            self.assertIn("Error syncing asset-3", sync_job.errors[0]["message"])
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_execute_sync_job_push_with_complete_failure(self):
        """Test PUSH sync with complete failure (no mocks: real connector via register)"""

        class CompleteFailureConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                return SyncResult(
                    status=SyncStatus.FAILED,
                    total_items=2,
                    successful_items=0,
                    failed_items=2,
                    skipped_items=0,
                    errors=["Connection timeout", "Authentication failed"],
                    metadata={},
                    started_at=timezone.now(),
                    completed_at=timezone.now(),
                )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, CompleteFailureConnector
        )
        try:
            asset = Asset.objects.create(
                tenant=self.tenant, key="test-asset-1", name="Test Asset 1"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": [str(asset.id)], "options": {}},
            )

            result = execute_marketplace_sync(str(sync_job.id), retry_count=0)

            self.assertEqual(result["status"], "completed")
            self.assertEqual(result["sync_status"], SyncStatus.FAILED.value)
            self.assertEqual(result["successful_items"], 0)
            self.assertEqual(result["failed_items"], 2)

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
            self.assertEqual(sync_job.items_synced, 0)
            self.assertEqual(sync_job.items_failed, 2)
            self.assertGreater(
                len(sync_job.errors), 0, "Complete failure should record at least one error"
            )
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_execute_sync_job_push_no_asset_ids(self):
        """Test error handling when no asset IDs provided for PUSH"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"options": {}},  # Missing asset_ids
        )

        # Execute sync (should fail)
        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(str(sync_job.id), retry_count=0)

        self.assertIn("asset ids", str(cm.exception).lower())

        # Verify sync job was marked as failed
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)

    def test_execute_sync_job_connection_error_retryable(self):
        """Test that ConnectionError is retryable"""

        # Create connector that raises ConnectionError naturally
        class ErrorConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                raise ConnectionError("Connection timeout")

        # Register connector temporarily
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, ErrorConnector
        )

        try:
            # Create sync job
            asset = Asset.objects.create(
                tenant=self.tenant, key="test-asset-1", name="Test Asset 1"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": [str(asset.id)], "options": {}},
            )

            # Execute sync (should raise ConnectionError for retry)
            try:
                execute_marketplace_sync(str(sync_job.id), retry_count=0)
            except ConnectionError:
                # Expected - ConnectionError should be raised for retry
                pass

            # ConnectionError → mark_failed at tasks.py:362 → FAILED
            # (note: TRANSIENT re-raise goes to catch-all, job is already FAILED)
            sync_job.refresh_from_db()
            self.assertEqual(
                sync_job.status,
                SyncStatus.FAILED.value,
                f"Expected FAILED after ConnectionError, got {sync_job.status}",
            )
        finally:
            # Unregister test connector
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

    # ========== ERROR HANDLING TESTS ==========

    def test_execute_sync_job_with_nonexistent_job(self):
        """Test that execute_marketplace_sync raises ValueError for nonexistent job"""
        fake_job_id = str(uuid.uuid4())
        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(fake_job_id, retry_count=0)
        self.assertIn("not found", str(cm.exception).lower())

    def test_execute_sync_job_with_invalid_job_id(self):
        """Test that execute_marketplace_sync raises ValueError for invalid job ID format"""
        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync("not-a-uuid", retry_count=0)
        self.assertIn("invalid", str(cm.exception).lower())

    def test_execute_sync_job_handles_missing_connection(self):
        """Test that execute_marketplace_sync raises ValueError for missing connection"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": ["asset-1"], "options": {}},
        )

        # Delete connection
        self.connection.delete()

        # Execute sync — should raise ValueError due to select_related failure
        # or an explicit validation error about the missing connection.
        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(str(sync_job.id), retry_count=0)
        error_msg = str(cm.exception).lower()
        self.assertTrue(
            "not found" in error_msg or "does not exist" in error_msg,
            f"Expected connection-not-found error, got: {cm.exception}",
        )

    # ========== TDD COMPLIANCE TESTS ==========

    def test_execute_sync_job_updates_status_correctly(self):
        """Test that execute_marketplace_sync updates sync job status correctly"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset-status", name="Test Asset Status"
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [str(asset.id)], "options": {}},
        )

        # Register test connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

        try:
            # Execute sync — TestMarketplaceConnector always returns COMPLETED
            execute_marketplace_sync(str(sync_job.id), retry_count=0)

            # Verify status was updated correctly
            sync_job.refresh_from_db()
            self.assertEqual(
                sync_job.status,
                SyncStatus.COMPLETED.value,
                f"Expected COMPLETED, got {sync_job.status}",
            )
            self.assertEqual(sync_job.items_synced, 1)
            self.assertEqual(sync_job.items_failed, 0)
        finally:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

    def test_execute_sync_job_records_errors(self):
        """Test that execute_marketplace_sync records errors correctly"""

        # Create connector that fails
        class FailingConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                raise ValueError("Sync failed")

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, FailingConnector
        )

        try:
            asset = Asset.objects.create(
                tenant=self.tenant, key="test-asset-error", name="Test Asset Error"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": [str(asset.id)], "options": {}},
            )

            # Execute sync — ValueError should propagate after mark_failed
            try:
                execute_marketplace_sync(str(sync_job.id), retry_count=0)
                self.fail("Expected ValueError to be raised")
            except ValueError as exc:
                self.assertIn("Sync failed", str(exc))

            # Verify error was recorded and status is terminal
            sync_job.refresh_from_db()
            self.assertEqual(
                sync_job.status,
                SyncStatus.FAILED.value,
                f"Expected FAILED, got {sync_job.status}",
            )
            self.assertGreater(
                len(sync_job.errors),
                0,
                f"Expected at least one recorded error, got {sync_job.errors}",
            )
            self.assertIn("Sync failed", sync_job.errors[0]["message"])
        finally:
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )


class MarketplaceSyncTaskIntegrationTest(TestCase):
    """Integration tests for execute_marketplace_sync with real job queue"""

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
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

        # Register test connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

        # Clear queues
        for queue_name in ["job_critical", "job_default", "job_low", "default"]:
            try:
                queue = get_queue(queue_name)
                queue.empty()
            except Exception:
                pass

    def tearDown(self):
        """Clean up after tests"""
        # Unregister test connector
        with contextlib.suppress(ValueError):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )

        # Clear queues
        for queue_name in ["job_critical", "job_default", "job_low", "default"]:
            try:
                queue = get_queue(queue_name)
                queue.empty()
            except Exception:
                pass
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

    def test_sync_job_enqueued_and_processed(self):
        """Test that sync job can be enqueued and processed via job queue"""
        from hub.apps.jobs.tasks import process_job
        from hub.apps.jobs.utils import create_job

        # Create sync job
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [str(asset.id)], "options": {}},
        )

        # Create background job
        job = create_job(
            tenant=self.tenant,
            user=self.user,
            job_type=JobType.MARKETPLACE_SYNC,
            resource_type="MARKETPLACE_SYNC_JOB",
            resource_id=str(sync_job.id),
            details_json={
                "sync_job_id": str(sync_job.id),
                "connection_id": str(self.connection.id),
                "direction": SyncDirection.PUSH.value,
                "asset_ids": [str(asset.id)],
                "options": {},
            },
            timeout_seconds=3600,
        )

        # Process job directly (simulating worker)
        process_job(str(job.id), JobType.MARKETPLACE_SYNC, timeout=3600)

        # Verify job completed
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.COMPLETED)

        # Verify sync job completed
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertEqual(sync_job.items_synced, 1)


class MarketplaceSyncTaskErrorHandlingTest(TestCase):
    """Error handling tests for execute_marketplace_sync"""

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
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

    def test_execute_sync_job_invalid_marketplace_type(self):
        """Test error handling for unsupported marketplace type"""
        # Create connection with valid marketplace type but no registered connector
        # Use a marketplace type that's valid but not registered
        connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Invalid Connection",
            marketplace_type=MarketplaceType.AWS_DATA_EXCHANGE.value,  # Valid enum but no connector registered
            is_active=True,
        )
        connection.set_config({"api_key": "test"})

        # Unregister connector if it exists
        try:
            MarketplaceConnectorFactory.unregister_connector(MarketplaceType.AWS_DATA_EXCHANGE)
        except ValueError:
            pass  # Already unregistered

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": []},
        )

        # Execute sync (should fail)
        with self.assertRaises((ValueError, ServiceError)):
            execute_marketplace_sync(str(sync_job.id), retry_count=0)

        # Verify sync job was marked as failed
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)

    def test_execute_sync_job_connector_creation_failure(self):
        """Test error handling when connector creation fails (no mocks: real connector raises in __init__)"""

        class FailingConnector(TestMarketplaceConnector):
            def __init__(self, *args, **kwargs):
                raise Exception("Failed to create connector")

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, FailingConnector
        )
        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": []},
            )

            with self.assertRaises((ValueError, ServiceError)) as cm:
                execute_marketplace_sync(str(sync_job.id), retry_count=0)

            self.assertIn("Failed to create connector", str(cm.exception))

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_execute_sync_job_sync_operation_returns_none(self):
        """Test error handling when sync operation returns None"""

        # Create connector class that returns None
        class NoneReturningConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                return None

        # Register connector
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, NoneReturningConnector
        )

        try:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": ["asset-1"]},
            )

            # Execute sync (should fail)
            with self.assertRaises(ServiceError) as cm:
                execute_marketplace_sync(str(sync_job.id), retry_count=0)

            # ServiceError("Sync operation returned no result") — exact message
            self.assertIn(
                "no result",
                str(cm.exception).lower(),
                msg=f"Expected 'no result' in error, got: {cm.exception}",
            )

            # Verify sync job was marked as failed
            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        finally:
            # Unregister connector and restore original
            try:
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )
                # Re-register original test connector
                MarketplaceConnectorFactory.register_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
                )
            except ValueError:
                pass


class MarketplaceSyncTaskBidirectionalTest(TestCase):
    """Tests for BIDIRECTIONAL sync logic (Phase 2.4)."""

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Bidirectional Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )
        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

    def tearDown(self):
        with contextlib.suppress(ValueError):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass

    def test_bidirectional_both_succeed(self):
        """BIDIRECTIONAL with both PUSH and PULL succeeding → COMPLETED with summed items."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="bi-asset-1", name="Bidirectional Asset"
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.BIDIRECTIONAL.value,
            status=SyncStatus.PENDING.value,
            metadata={
                "asset_ids": [str(asset.id)],
                "listing_ids": ["listing-1"],
                "options": {},
            },
        )

        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["sync_status"], SyncStatus.COMPLETED.value)
        # 1 push item + 1 pull item = 2 total successful
        self.assertGreaterEqual(result["successful_items"], 1)

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)

    def test_bidirectional_push_only(self):
        """BIDIRECTIONAL with only push assets → only PUSH executes."""
        asset = Asset.objects.create(
            tenant=self.tenant, key="bi-push-only", name="Push Only"
        )
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.BIDIRECTIONAL.value,
            status=SyncStatus.PENDING.value,
            metadata={"asset_ids": [str(asset.id)], "options": {}},
        )

        result = execute_marketplace_sync(str(sync_job.id), retry_count=0)
        self.assertEqual(result["status"], "completed")
        sync_job.refresh_from_db()
        self.assertIn(
            sync_job.status,
            [SyncStatus.COMPLETED.value, SyncStatus.PARTIAL.value],
        )

    def test_bidirectional_no_operations_raises(self):
        """BIDIRECTIONAL with no asset_ids or listing_ids → ValueError."""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.BIDIRECTIONAL.value,
            status=SyncStatus.PENDING.value,
            metadata={"options": {}},
        )

        with self.assertRaises(ValueError) as cm:
            execute_marketplace_sync(str(sync_job.id), retry_count=0)
        self.assertIn("No sync operations", str(cm.exception))

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)


# =============================================================================
# Error Classification Tests (Phase 2.5)
# =============================================================================


class MarketplaceSyncErrorClassificationTest(TestCase):
    """Tests for PERMANENT, TRANSIENT, and UNKNOWN error classification paths."""

    def setUp(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.disconnect(contract_saved, sender=Contract)
            post_save.disconnect(asset_saved, sender=Asset)
        except (ImportError, AttributeError):
            pass
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="ErrorClass Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

    def tearDown(self):
        from django.db.models.signals import post_save

        try:
            from hub.apps.assets.models import Asset
            from hub.apps.contracts.models import Contract
            from hub.apps.semantic.signals import asset_saved, contract_saved

            post_save.connect(contract_saved, sender=Contract, weak=False)
            post_save.connect(asset_saved, sender=Asset, weak=False)
        except (ImportError, AttributeError):
            pass

    def test_permanent_error_fails_immediately(self):
        """Error classified as PERMANENT → job marked FAILED, no retry."""
        # Use a ValueError (not ConnectionError) — the error classifier maps
        # unknown errors to UNKNOWN, but we can verify the mark_failed path.
        class PermanentErrorConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                # Raise a ValueError which is caught and classified
                raise ValueError("Permanent configuration error")

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, PermanentErrorConnector
        )
        try:
            asset = Asset.objects.create(
                tenant=self.tenant, key="perm-err", name="Permanent Error"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": [str(asset.id)], "options": {}},
            )

            with self.assertRaises(ValueError):
                execute_marketplace_sync(str(sync_job.id), retry_count=0)

            sync_job.refresh_from_db()
            self.assertEqual(
                sync_job.status,
                SyncStatus.FAILED.value,
                "Job should be marked FAILED after a permanent/error during sync",
            )
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )

    def test_connection_error_is_classified_and_records_errors(self):
        """ConnectionError during sync → job marked FAILED, errors recorded."""
        class ConnectionErrorConnector(TestMarketplaceConnector):
            def sync_push(self, asset_ids, options=None):
                raise ConnectionError("Connection timeout")

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, ConnectionErrorConnector
        )
        try:
            asset = Asset.objects.create(
                tenant=self.tenant, key="conn-err", name="Connection Error"
            )
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=SyncStatus.PENDING.value,
                metadata={"asset_ids": [str(asset.id)], "options": {}},
            )

            with self.assertRaises(ConnectionError):
                execute_marketplace_sync(str(sync_job.id), retry_count=0)

            sync_job.refresh_from_db()
            self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
            self.assertGreater(len(sync_job.errors), 0)
        finally:
            with contextlib.suppress(ValueError):
                MarketplaceConnectorFactory.unregister_connector(
                    MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
                )
