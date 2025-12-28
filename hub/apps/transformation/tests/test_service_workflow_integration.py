"""
Integration tests for TransformationService workflow integration.

Tests verify:
1. TransformationService.execute_pipeline() uses workflow
2. Workflow instance tracking in PipelineExecution
3. Workflow state management and synchronization
4. Status synchronization from workflow to execution
5. Workflow progress tracking
6. Workflow state retrieval

All tests use real services (no mocks) to ensure comprehensive integration.
"""
import uuid
from django.test import TestCase
from django.utils import timezone

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineExecution,
    PipelineStatus,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus
from hub.apps.orchestration.workflows.transformation_pipeline import TransformationPipelineWorkflow
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy
from django.contrib.auth import get_user_model

User = get_user_model()


class ServiceWorkflowIntegrationTest(TestCase):
    """Test service-workflow integration"""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        # Create DATA_PROVIDER role
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

        # Assign role to user
        UserRole.objects.create(
            user=self.user,
            role=self.data_provider_role
        )

        # Create access policy
        AccessPolicy.objects.get_or_create(
            tenant=self.tenant,
            name="Allow Pipeline Operations",
            defaults={
                "conditions": {
                    "user": {"tenant_id": str(self.tenant.id)}
                },
                "effect": "ALLOW",
                "priority": 100,
                "enabled": True,
                "created_by": self.user
            }
        )

        # Create CSV file content
        self.csv_content = b"id,name,age\n1,Alice,25\n2,Bob,17\n3,Charlie,30"

        # Create file first
        self.file = File.objects.create(
            name="test.csv",
            tenant=self.tenant,
            status=FileStatus.PENDING,
            size=len(self.csv_content),
            content_type="text/csv",
            storage_path=f"test/integration/{self.tenant.id}/test.csv",
            created_by=self.user
        )

        # Upload file to storage (real service)
        from hub.apps.files.storage import S3StorageClient

        try:
            storage_client = S3StorageClient()
            # save_file returns the storage path (key) used
            storage_path = storage_client.save_file(
                tenant_id=str(self.tenant.id),
                file_id=str(self.file.id),
                file_content=self.csv_content
            )
            # Update file with the actual storage path used
            self.file.storage_path = storage_path
            self.file.status = FileStatus.ACTIVE
            self.file.save()
            self.storage_available = True
        except Exception as e:
            # Storage might not be available, tests will skip
            self.storage_available = False
            self.storage_error = str(e)

        # Create asset first
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create dataset (requires file, format, and optionally asset)
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            asset=self.asset,
            created_by=self.user
        )

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            name="Test Pipeline",
            tenant=self.tenant,
            status=PipelineStatus.ACTIVE,
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "node_config": {
                            "operation": "transform"
                        }
                    }
                ]
            },
            version="1.0.0",
            created_by=self.user
        )

    def test_execute_pipeline_creates_workflow_instance(self):
        """Test that execute_pipeline creates and links workflow instance."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Verify execution was created
        self.assertIsNotNone(execution)
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.asset)

        # Verify workflow instance was created and linked
        self.assertIsNotNone(execution.workflow_instance)
        self.assertEqual(
            execution.workflow_instance.workflow_name,
            TransformationPipelineWorkflow.WORKFLOW_NAME
        )

    def test_workflow_instance_tracking(self):
        """Test workflow instance tracking methods."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Test get_workflow_instance
        workflow_instance = execution.get_workflow_instance()
        self.assertIsNotNone(workflow_instance)
        self.assertEqual(workflow_instance, execution.workflow_instance)

        # Test set_workflow_instance
        new_workflow_instance = WorkflowInstance.objects.create(
            workflow_definition_id=workflow_instance.workflow_definition_id,
            workflow_name=workflow_instance.workflow_name,
            workflow_version=workflow_instance.workflow_version,
            tenant=self.tenant,
            status=WorkflowStatus.DRAFT
        )
        execution.set_workflow_instance(new_workflow_instance)
        execution.refresh_from_db()
        self.assertEqual(execution.workflow_instance, new_workflow_instance)

    def test_sync_status_from_workflow(self):
        """Test status synchronization from workflow to execution."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Get workflow instance
        workflow_instance = execution.workflow_instance
        self.assertIsNotNone(workflow_instance)

        # Test sync when workflow is RUNNING
        workflow_instance.status = WorkflowStatus.RUNNING
        workflow_instance.started_at = timezone.now()
        workflow_instance.save()

        execution.status = ExecutionStatus.PENDING
        execution.save()

        updated = execution.sync_status_from_workflow()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)

        # Test sync when workflow is COMPLETED
        workflow_instance.status = WorkflowStatus.COMPLETED
        workflow_instance.completed_at = timezone.now()
        workflow_instance.save()

        updated = execution.sync_status_from_workflow()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)

        # Test sync when workflow is FAILED
        workflow_instance.status = WorkflowStatus.FAILED
        workflow_instance.error_message = "Test error"
        workflow_instance.save()

        execution.status = ExecutionStatus.RUNNING
        execution.save()

        updated = execution.sync_status_from_workflow()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

        # Test sync when workflow is CANCELLED
        workflow_instance.status = WorkflowStatus.CANCELLED
        workflow_instance.save()

        execution.status = ExecutionStatus.RUNNING
        execution.save()

        updated = execution.sync_status_from_workflow()
        self.assertTrue(updated)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)

    def test_get_workflow_progress(self):
        """Test workflow progress retrieval."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Test get_workflow_progress
        progress = execution.get_workflow_progress()
        self.assertIsNotNone(progress)
        self.assertGreaterEqual(progress, 0.0)
        self.assertLessEqual(progress, 100.0)

        # Test with no workflow instance
        execution.workflow_instance = None
        execution.save()
        progress = execution.get_workflow_progress()
        self.assertIsNone(progress)

    def test_get_workflow_state(self):
        """Test workflow state retrieval."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Test get_workflow_state
        state = execution.get_workflow_state()
        self.assertIsNotNone(state)
        self.assertIsInstance(state, dict)

        # Test with no workflow instance
        execution.workflow_instance = None
        execution.save()
        state = execution.get_workflow_state()
        self.assertIsNone(state)

    def test_workflow_state_management(self):
        """Test workflow state management methods."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Verify workflow instance has state_data
        workflow_instance = execution.workflow_instance
        self.assertIsNotNone(workflow_instance)
        self.assertIsNotNone(workflow_instance.state_data)
        self.assertIsInstance(workflow_instance.state_data, dict)

        # Verify execution_id is in state_data
        self.assertIn("execution_id", workflow_instance.state_data)
        self.assertEqual(
            workflow_instance.state_data["execution_id"],
            str(execution.id)
        )

    def test_execution_without_workflow_instance(self):
        """Test execution methods work when workflow_instance is None."""
        # Create execution without workflow instance
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING,
            execution_mode=ExecutionMode.SYNC
        )

        # Test sync_status_from_workflow returns False
        updated = execution.sync_status_from_workflow()
        self.assertFalse(updated)

        # Test get_workflow_progress returns None
        progress = execution.get_workflow_progress()
        self.assertIsNone(progress)

        # Test get_workflow_state returns None
        state = execution.get_workflow_state()
        self.assertIsNone(state)

    def test_workflow_instance_persistence(self):
        """Test that workflow instance persists across execution updates."""
        service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Execute pipeline
        execution = service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.SYNC
        )

        # Get workflow instance ID
        workflow_instance_id = execution.workflow_instance.id

        # Update execution
        execution.add_log_entry("Test log entry", "INFO")
        execution.save()

        # Verify workflow instance is still linked
        execution.refresh_from_db()
        self.assertIsNotNone(execution.workflow_instance)
        self.assertEqual(execution.workflow_instance.id, workflow_instance_id)

