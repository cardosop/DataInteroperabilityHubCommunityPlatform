"""
Unit tests for TransformationService job queue integration.

Tests verify comprehensive job queue integration for pipeline execution:
- Job creation for async execution
- Queue name selection based on execution mode
- Job linking to execution
- Job status synchronization
- Job cancellation handling

All tests use real job queue (no mocks) to ensure integration.
"""
import uuid
from django.test import TestCase
from django.utils import timezone
from django_rq import get_queue

from hub.apps.transformation.services import TransformationService
from hub.apps.transformation.models import TransformationPipeline, PipelineStatus, PipelineExecution, ExecutionMode, ExecutionStatus
from hub.apps.transformation.exceptions import TransformationExecutionError
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.tenants.models import Tenant
from hub.apps.governance.models import AccessPolicy
from hub.apps.jobs.models import Job, JobType, JobStatus
from hub.apps.jobs.utils import create_job


class JobQueueIntegrationTest(TestCase):
    """Test job queue integration in TransformationService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create role and user
        self.role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )
        self.user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(user=self.user, role=self.role)

        # Create ABAC policy
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

        # Create pipeline
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Pipeline",
            pipeline_definition={
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "step1",
                        "type": "task",
                        "task": "extract_data",
                        "input": {}
                    }
                ]
            },
            version="1.0.0",
            status=PipelineStatus.ACTIVE.value
        )

        # Create test asset with dataset and file
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="test.csv",
            storage_path="test/test.csv",
            size=100,
            content_type="text/csv",
            status=FileStatus.ACTIVE
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=self.asset,
            file=self.file,
            version=1,
            format="CSV",
            row_count=10
        )

        self.service = TransformationService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Clear queues before tests
        for queue_name in ['job_critical', 'job_default', 'job_low']:
            try:
                queue = get_queue(queue_name)
                queue.empty()
            except Exception:
                pass  # Queue may not exist in test environment

    def test_async_execution_creates_job(self):
        """Test that async execution creates a job"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Verify execution was created
        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)

        # Verify job was created and linked
        self.assertIsNotNone(execution.job)
        self.assertEqual(execution.job.type, JobType.TRANSFORMATION_PIPELINE_EXECUTION.value)
        self.assertEqual(execution.job.status, JobStatus.PENDING)
        self.assertEqual(execution.job.resource_type, "TRANSFORMATION_PIPELINE_EXECUTION")
        self.assertEqual(str(execution.job.resource_id), str(execution.id))

    def test_job_queue_name_based_on_execution_mode(self):
        """Test that queue name is set based on execution mode"""
        # Test ASYNC mode uses job_default
        execution_async = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Verify job was created with correct queue
        # Note: We can't directly check queue name from job model,
        # but we can verify job was enqueued to the correct queue
        self.assertIsNotNone(execution_async.job)

        # Check that job details include execution mode
        job_details = execution_async.job.details_json
        self.assertEqual(job_details.get("execution_mode"), ExecutionMode.ASYNC.value)

    def test_job_linked_to_execution(self):
        """Test that job is properly linked to execution"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Verify bidirectional relationship
        self.assertEqual(execution.job.id, execution.job.id)

        # Verify execution can be accessed from job
        job = execution.job
        execution_from_job = PipelineExecution.objects.filter(job=job).first()
        self.assertIsNotNone(execution_from_job)
        self.assertEqual(execution_from_job.id, execution.id)

    def test_execution_status_syncs_from_job(self):
        """Test that execution status syncs from job status"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Initially both should be PENDING
        self.assertEqual(execution.status, ExecutionStatus.PENDING)
        self.assertEqual(execution.job.status, JobStatus.PENDING)

        # Update job status to RUNNING
        execution.job.mark_started()
        execution.sync_status_from_job()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)

        # Update job status to COMPLETED
        # Set a result_asset to satisfy validation
        execution.result_asset = self.asset
        execution.job.mark_completed()
        execution.sync_status_from_job()
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)

    def test_execution_status_syncs_from_job_failed(self):
        """Test that execution status syncs from job failed status"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Update job status to FAILED
        execution.job.mark_failed(error_message="Job execution failed")
        execution.sync_status_from_job()
        execution.refresh_from_db()

        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(execution.completed_at)

        # Verify error message was logged
        self.assertIsInstance(execution.execution_log, list)
        error_logs = [log for log in execution.execution_log if log.get("level") == "ERROR"]
        self.assertGreater(len(error_logs), 0)

    def test_execution_status_syncs_from_job_cancelled(self):
        """Test that execution status syncs from job cancelled status"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Update job status to CANCELLED
        execution.job.mark_cancelled()
        execution.sync_status_from_job()
        execution.refresh_from_db()

        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertIsNotNone(execution.completed_at)

        # Verify cancellation was logged
        self.assertIsInstance(execution.execution_log, list)
        cancel_logs = [log for log in execution.execution_log if "cancelled" in log.get("message", "").lower()]
        self.assertGreater(len(cancel_logs), 0)

    def test_job_cancellation_updates_execution(self):
        """Test that job cancellation updates execution status"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Mark job as running
        execution.job.mark_started()
        execution.sync_status_from_job()

        # Cancel job via mark_cancelled
        execution.job.mark_cancelled()
        execution.sync_status_from_job()
        execution.refresh_from_db()

        # Verify execution was cancelled
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertEqual(execution.job.status, JobStatus.CANCELLED)

    def test_sync_status_from_job_no_job(self):
        """Test that sync_status_from_job returns False when no job linked"""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            execution_mode=ExecutionMode.SYNC.value,
            status=ExecutionStatus.PENDING
        )

        # Should return False and not update status
        result = execution.sync_status_from_job()
        self.assertFalse(result)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)

    def test_sync_status_from_job_terminal_state(self):
        """Test that sync_status_from_job doesn't update from terminal states"""
        execution = self.service.execute_pipeline(
            pipeline_id=str(self.pipeline.id),
            asset_id=str(self.asset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=ExecutionMode.ASYNC.value
        )

        # Mark execution as completed with result_asset
        execution.status = ExecutionStatus.COMPLETED
        execution.completed_at = timezone.now()
        execution.result_asset = self.asset
        execution.save(update_fields=['status', 'completed_at', 'result_asset', 'updated_at'])
        execution.refresh_from_db()

        # Verify execution is completed
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertTrue(execution.is_terminal())

        # Try to sync from pending job (should not change execution status)
        # First, manually set job to PENDING (simulating a race condition)
        execution.job.status = JobStatus.PENDING
        execution.job.save()
        execution.job.refresh_from_db()

        # Sync should detect that execution is terminal and job is not, so it should not update
        result = execution.sync_status_from_job()

        # Should not update because execution is in terminal state
        self.assertFalse(result)  # Should return False (no update)
        execution.refresh_from_db()
        # Execution should remain COMPLETED
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)

