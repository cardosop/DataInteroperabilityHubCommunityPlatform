"""
Integration tests for MarketplaceIntegrationService workflow integration.

Tests the integration between MarketplaceIntegrationService and MarketplaceSyncWorkflow,
including workflow instance creation, status syncing, and progress tracking.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetSourceType, AssetStatus
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceMapping,
    MarketplaceSyncJob,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.registry import WorkflowRegistry
from hub.apps.orchestration.workflow_engine import WorkflowEngine
from hub.apps.orchestration.workflows.marketplace_sync import MarketplaceSyncWorkflow
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class MarketplaceServiceWorkflowIntegrationTest(TestCase):
    """Integration tests for service-workflow integration"""

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

        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass", tenant=self.tenant
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.orchestration.tests.test_marketplace_sync_workflow import (
            TestMarketplaceConnector,
        )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

        # Initialize workflow engine and registry
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        MarketplaceSyncWorkflow.register_workflow(self.registry)
        MarketplaceSyncWorkflow.register_tasks(self.engine)

    def test_sync_assets_to_marketplace_creates_workflow_instance(self):
        """Test that sync_assets_to_marketplace creates workflow instance"""
        # Create test asset (key required, unique per tenant)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="workflow-instance-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Call service method
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        # Verify sync job was created
        self.assertIsNotNone(sync_job.id)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)

        # Verify workflow instance ID is stored in metadata
        self.assertIn("workflow_instance_id", sync_job.metadata)
        workflow_instance_id = sync_job.metadata["workflow_instance_id"]

        # Verify workflow instance exists
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        self.assertEqual(workflow_instance.workflow_name, "marketplace_sync_push")
        self.assertEqual(workflow_instance.tenant_id, self.tenant.id)
        self.assertEqual(str(workflow_instance.input_data["sync_job_id"]), str(sync_job.id))
        self.assertEqual(workflow_instance.input_data["connection_id"], str(self.connection.id))
        self.assertEqual(workflow_instance.input_data["asset_ids"], [str(asset.id)])

        # Verify workflow instance was started (may complete synchronously in tests)
        self.assertIn(
            workflow_instance.status,
            (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED),
            f"Workflow should be RUNNING or COMPLETED, got {workflow_instance.status}",
        )

    def test_sync_from_marketplace_creates_workflow_instance(self):
        """Test that sync_from_marketplace creates workflow instance"""
        # Call service method
        sync_job = self.service.sync_from_marketplace(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=["listing-1", "listing-2"],
        )

        # Verify sync job was created
        self.assertIsNotNone(sync_job.id)
        self.assertEqual(sync_job.direction, SyncDirection.PULL.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)

        # Verify workflow instance ID is stored in metadata
        self.assertIn("workflow_instance_id", sync_job.metadata)
        workflow_instance_id = sync_job.metadata["workflow_instance_id"]

        # Verify workflow instance exists
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)
        self.assertEqual(workflow_instance.workflow_name, "marketplace_sync_pull")
        self.assertEqual(workflow_instance.tenant_id, self.tenant.id)
        self.assertEqual(str(workflow_instance.input_data["sync_job_id"]), str(sync_job.id))
        self.assertEqual(workflow_instance.input_data["connection_id"], str(self.connection.id))
        self.assertEqual(workflow_instance.input_data["listing_ids"], ["listing-1", "listing-2"])

        # Verify workflow instance was started (may complete synchronously in tests)
        self.assertIn(
            workflow_instance.status,
            (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED),
            f"Workflow should be RUNNING or COMPLETED, got {workflow_instance.status}",
        )

    def test_sync_workflow_status_to_sync_job_completed(self):
        """Test syncing workflow status to sync job when workflow completes"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"workflow_instance_id": None},
        )

        # Create workflow instance
        workflow_instance = self.engine.create_instance(
            workflow_name="marketplace_sync_push",
            input_data={
                "connection_id": str(self.connection.id),
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Update sync job metadata with workflow instance ID
        sync_job.metadata["workflow_instance_id"] = str(workflow_instance.id)
        sync_job.save(update_fields=["metadata"])

        # Mark workflow as completed
        workflow_instance.mark_completed(output_data={})

        # Sync workflow status to sync job
        updated_sync_job = self.service.sync_workflow_status_to_sync_job(
            sync_job_id=str(sync_job.id), tenant_id=str(self.tenant.id)
        )

        # Verify sync job status was updated
        self.assertEqual(updated_sync_job.status, SyncStatus.COMPLETED.value)
        self.assertIsNotNone(updated_sync_job.completed_at)

    def test_sync_workflow_status_to_sync_job_failed(self):
        """Test syncing workflow status to sync job when workflow fails"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"workflow_instance_id": None},
        )

        # Create workflow instance
        workflow_instance = self.engine.create_instance(
            workflow_name="marketplace_sync_push",
            input_data={
                "connection_id": str(self.connection.id),
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Update sync job metadata with workflow instance ID
        sync_job.metadata["workflow_instance_id"] = str(workflow_instance.id)
        sync_job.save(update_fields=["metadata"])

        # Mark workflow as failed
        workflow_instance.mark_failed(
            error_message="Test error", error_details={"error": "Test failure"}
        )

        # Sync workflow status to sync job
        updated_sync_job = self.service.sync_workflow_status_to_sync_job(
            sync_job_id=str(sync_job.id), tenant_id=str(self.tenant.id)
        )

        # Verify sync job status was updated
        self.assertEqual(updated_sync_job.status, SyncStatus.FAILED.value)
        self.assertIsNotNone(updated_sync_job.completed_at)
        self.assertGreater(len(updated_sync_job.errors), 0)
        # Errors are stored as dictionaries with 'message' field
        error_message = updated_sync_job.errors[0]
        if isinstance(error_message, dict):
            self.assertIn("Test error", error_message.get("message", ""))
        else:
            self.assertIn("Test error", str(error_message))

    def test_update_sync_job_progress(self):
        """Test updating sync job progress"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
        )

        # Update progress
        updated_sync_job = self.service.update_sync_job_progress(
            sync_job_id=str(sync_job.id),
            progress_percentage=50,
            current_step="map_assets_to_marketplace",
            tenant_id=str(self.tenant.id),
        )

        # Verify progress was updated
        self.assertEqual(updated_sync_job.metadata["progress_percentage"], 50)
        self.assertEqual(updated_sync_job.metadata["current_step"], "map_assets_to_marketplace")

    def test_update_sync_job_progress_bounds(self):
        """Test that progress is bounded between 0 and 100"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
        )

        # Update progress with out-of-bounds values
        updated_sync_job = self.service.update_sync_job_progress(
            sync_job_id=str(sync_job.id),
            progress_percentage=150,  # Over 100
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(updated_sync_job.metadata["progress_percentage"], 100)

        updated_sync_job = self.service.update_sync_job_progress(
            sync_job_id=str(sync_job.id),
            progress_percentage=-10,  # Under 0
            tenant_id=str(self.tenant.id),
        )
        self.assertEqual(updated_sync_job.metadata["progress_percentage"], 0)


@override_settings(
    EVENT_BUS_ENABLE_PERSISTENCE=True,
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
)
class MarketplaceSyncE2ETest(TestCase):
    """E2E tests for complete sync operations with workflow"""

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

        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="VERIFIED"
        )
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass", tenant=self.tenant
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
            is_active=True,
        )
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.orchestration.tests.test_marketplace_sync_workflow import (
            TestMarketplaceConnector,
        )

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

        # Initialize workflow engine and registry
        self.engine = WorkflowEngine()
        self.registry = WorkflowRegistry()
        MarketplaceSyncWorkflow.register_workflow(self.registry)
        MarketplaceSyncWorkflow.register_tasks(self.engine)

    def test_push_sync_e2e(self):
        """Test complete PUSH sync operation end-to-end"""
        # Create test asset (key required, unique per tenant)
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="push-sync-e2e-asset",
            name="Test Asset",
            description="Test Description",
            status=AssetStatus.ACTIVE,
            source_type=AssetSourceType.HUB_NATIVE,
        )

        # Call service method to start sync
        sync_job = self.service.sync_assets_to_marketplace(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_ids=[str(asset.id)],
        )

        # Verify sync job was created with workflow instance
        self.assertIsNotNone(sync_job.id)
        self.assertIn("workflow_instance_id", sync_job.metadata)
        workflow_instance_id = sync_job.metadata["workflow_instance_id"]

        # Get workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow was started (may complete synchronously in tests)
        self.assertIn(
            workflow_instance.status,
            (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED),
            f"Workflow should be RUNNING or COMPLETED, got {workflow_instance.status}",
        )

    def test_pull_sync_e2e(self):
        """Test complete PULL sync operation end-to-end"""
        # Call service method to start sync
        sync_job = self.service.sync_from_marketplace(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            listing_ids=["listing-1"],
        )

        # Verify sync job was created with workflow instance
        self.assertIsNotNone(sync_job.id)
        self.assertIn("workflow_instance_id", sync_job.metadata)
        workflow_instance_id = sync_job.metadata["workflow_instance_id"]

        # Get workflow instance
        workflow_instance = WorkflowInstance.objects.get(id=workflow_instance_id)

        # Verify workflow was started (may complete synchronously in tests)
        self.assertIn(
            workflow_instance.status,
            (WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED),
            f"Workflow should be RUNNING or COMPLETED, got {workflow_instance.status}",
        )

    def test_workflow_progress_tracking(self):
        """Test that workflow progress is tracked in sync job"""
        # Create sync job
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"workflow_instance_id": None},
        )

        # Create workflow instance
        workflow_instance = self.engine.create_instance(
            workflow_name="marketplace_sync_push",
            input_data={
                "connection_id": str(self.connection.id),
                "sync_job_id": str(sync_job.id),
                "tenant_id": str(self.tenant.id),
                "user_id": str(self.user.id),
            },
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id),
        )

        # Update sync job metadata with workflow instance ID
        sync_job.metadata["workflow_instance_id"] = str(workflow_instance.id)
        sync_job.save(update_fields=["metadata"])

        # Simulate workflow progress updates
        workflow_instance.state_data = {
            "sync_job_id": str(sync_job.id),
            "progress_percentage": 25,
            "current_step_name": "validate_assets",
        }
        workflow_instance.save(update_fields=["state_data"])

        # Sync workflow status (which also syncs progress)
        updated_sync_job = self.service.sync_workflow_status_to_sync_job(
            sync_job_id=str(sync_job.id), tenant_id=str(self.tenant.id)
        )

        # Verify progress was synced
        self.assertEqual(updated_sync_job.metadata.get("progress_percentage"), 25)
        self.assertEqual(updated_sync_job.metadata.get("current_step"), "validate_assets")

    def test_workflow_integration_error_handling(self):
        """Test error handling in workflow integration"""
        import uuid as uuid_module

        from hub.apps.core.services.base import NotFoundError

        # Test with non-existent sync job ID (valid UUID format)
        non_existent_id = str(uuid_module.uuid4())
        with self.assertRaises(NotFoundError):
            self.service.sync_workflow_status_to_sync_job(
                sync_job_id=non_existent_id, tenant_id=str(self.tenant.id)
            )

    def test_workflow_integration_with_missing_workflow_instance(self):
        """Test workflow integration when workflow instance doesn't exist"""
        # Create sync job without workflow instance
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"workflow_instance_id": None},
        )

        # Sync workflow status - should handle missing workflow gracefully
        updated_sync_job = self.service.sync_workflow_status_to_sync_job(
            sync_job_id=str(sync_job.id), tenant_id=str(self.tenant.id)
        )

        # Sync job should remain in PENDING status if workflow doesn't exist
        self.assertEqual(updated_sync_job.status, SyncStatus.PENDING.value)

    def test_update_sync_job_progress_with_invalid_sync_job(self):
        """Test updating progress with non-existent sync job ID"""
        import uuid as uuid_module

        from hub.apps.core.services.base import NotFoundError

        non_existent_id = str(uuid_module.uuid4())
        with self.assertRaises(NotFoundError):
            self.service.update_sync_job_progress(
                sync_job_id=non_existent_id,
                progress_percentage=50,
                tenant_id=str(self.tenant.id),
            )

    def test_sync_assets_to_marketplace_with_invalid_connection(self):
        """Test sync_assets_to_marketplace with invalid connection"""
        from hub.apps.core.services.base import NotFoundError

        asset = Asset.objects.create(
            tenant=self.tenant,
            key="invalid-conn-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            source_type=AssetSourceType.HUB_NATIVE,
        )

        with self.assertRaises(NotFoundError):
            self.service.sync_assets_to_marketplace(
                connection_id="invalid-connection-id",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_ids=[str(asset.id)],
            )

    def test_sync_from_marketplace_with_invalid_connection(self):
        """Test sync_from_marketplace with invalid connection"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.sync_from_marketplace(
                connection_id="invalid-connection-id",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                listing_ids=["listing-1"],
            )

    def test_sync_workflow_status_edge_cases(self):
        """Test edge cases in workflow status syncing"""
        # Create sync job with invalid workflow instance ID
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            metadata={"workflow_instance_id": "invalid-workflow-id"},
        )

        # Should handle invalid workflow instance ID gracefully
        updated_sync_job = self.service.sync_workflow_status_to_sync_job(
            sync_job_id=str(sync_job.id), tenant_id=str(self.tenant.id)
        )

        # Sync job should remain unchanged if workflow doesn't exist
        self.assertEqual(updated_sync_job.status, SyncStatus.PENDING.value)

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
