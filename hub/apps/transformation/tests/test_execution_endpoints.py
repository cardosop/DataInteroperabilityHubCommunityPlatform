"""
Unit tests for Pipeline Execution API Endpoints.

Tests all execution endpoints using real services and models (no mocks/stubs).
"""
import uuid
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.transformation.models import (
    TransformationPipeline,
    PipelineExecution,
    PipelineStatus,
    ExecutionStatus,
    ExecutionMode
)
from hub.apps.transformation.serializers import (
    PipelineExecutionSerializer,
    PipelineExecutionProgressSerializer,
    PipelineExecutionResultSerializer
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, Role, UserRole
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.governance.models import AccessPolicy

User = get_user_model()


class PipelineExecutionEndpointsTest(TestCase):
    """Test cases for pipeline execution API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )

        # Create DATA_PROVIDER role
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.get_or_create(
            user=self.user,
            role=self.data_provider_role
        )

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
                        "node_config": {
                            "node_type": "filter",
                            "filter_expression": "age > 18"
                        }
                    }
                ]
            },
            status=PipelineStatus.ACTIVE
        )

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Authenticate client
        self.client.force_authenticate(user=self.user)

    def test_list_executions_success(self):
        """Test listing executions for a pipeline."""
        # Create result asset for completed execution
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create some executions
        execution1 = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            execution_mode=ExecutionMode.ASYNC,
            result_asset=result_asset
        )
        execution2 = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING,
            execution_mode=ExecutionMode.SYNC
        )

        url = f'/api/v1/transformation/pipelines/{self.pipeline.id}/executions/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('count', response.data)
        self.assertIn('results', response.data)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_executions_with_status_filter(self):
        """Test listing executions with status filter."""
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset
        )
        PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING
        )

        url = f'/api/v1/transformation/pipelines/{self.pipeline.id}/executions/?status=COMPLETED'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['status'], ExecutionStatus.COMPLETED)

    def test_list_executions_pagination(self):
        """Test listing executions with pagination."""
        # Create result asset for completed executions
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        # Create multiple executions
        for i in range(25):
            PipelineExecution.objects.create(
                pipeline=self.pipeline,
                asset=self.asset,
                status=ExecutionStatus.COMPLETED,
                result_asset=result_asset
            )

        url = f'/api/v1/transformation/pipelines/{self.pipeline.id}/executions/?page_size=10'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 25)
        self.assertEqual(len(response.data['results']), 10)
        self.assertIsNotNone(response.data['next'])

    def test_list_executions_pipeline_not_found(self):
        """Test listing executions for non-existent pipeline."""
        invalid_id = str(uuid.uuid4())
        url = f'/api/v1/transformation/pipelines/{invalid_id}/executions/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_execution_details_success(self):
        """Test getting execution details."""
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            execution_mode=ExecutionMode.ASYNC,
            result_asset=result_asset
        )

        url = f'/api/v1/transformation/executions/{execution.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(execution.id))
        self.assertEqual(response.data['status'], ExecutionStatus.COMPLETED)
        self.assertEqual(response.data['pipeline_id'], str(self.pipeline.id))
        self.assertEqual(response.data['asset_id'], str(self.asset.id))

    def test_get_execution_details_not_found(self):
        """Test getting non-existent execution."""
        invalid_id = str(uuid.uuid4())
        url = f'/api/v1/transformation/executions/{invalid_id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_cancel_execution_success(self):
        """Test cancelling a pending execution."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        url = f'/api/v1/transformation/executions/{execution.id}/cancel/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.CANCELLED)
        self.assertIn('message', response.data)

        # Verify execution was cancelled
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)

    def test_cancel_execution_running(self):
        """Test cancelling a running execution."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING
        )

        url = f'/api/v1/transformation/executions/{execution.id}/cancel/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.CANCELLED)

        # Verify execution was cancelled
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)

    def test_cancel_execution_already_completed(self):
        """Test cancelling a completed execution (should fail)."""
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset
        )

        url = f'/api/v1/transformation/executions/{execution.id}/cancel/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

        # Verify execution status unchanged
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)

    def test_cancel_execution_with_job(self):
        """Test cancelling execution with associated job."""
        from hub.apps.jobs.models import Job, JobStatus, JobType
        from django.core.cache import cache

        # Create job
        job = Job.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            type=JobType.TRANSFORMATION_PIPELINE_EXECUTION,
            status=JobStatus.RUNNING,
            resource_id=str(uuid.uuid4())
        )

        # Set running counter
        running_key = f"job:tenant:{self.tenant.id}:running"
        cache.set(running_key, 1, timeout=3600)

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING,
            job=job
        )

        url = f'/api/v1/transformation/executions/{execution.id}/cancel/'
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify execution and job were cancelled
        execution.refresh_from_db()
        job.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertEqual(job.status, JobStatus.CANCELLED)

        # Clean up
        cache.set(running_key, 0, timeout=3600)

    def test_get_execution_progress_pending(self):
        """Test getting progress for pending execution."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.PENDING
        )

        url = f'/api/v1/transformation/executions/{execution.id}/progress/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.PENDING)
        self.assertEqual(response.data['progress_percentage'], 0.0)
        self.assertIn('total_steps', response.data)

    def test_get_execution_progress_running(self):
        """Test getting progress for running execution."""
        from django.utils import timezone
        from datetime import timedelta

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now() - timedelta(seconds=30)
        )

        url = f'/api/v1/transformation/executions/{execution.id}/progress/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.RUNNING)
        self.assertIsNotNone(response.data['progress_percentage'])
        self.assertIn('duration_seconds', response.data)
        self.assertIn('recent_logs', response.data)

    def test_get_execution_progress_with_metrics(self):
        """Test getting progress with metrics."""
        from django.utils import timezone

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now()
        )
        execution.update_metrics(
            progress_percentage=50.0,
            current_step="step1"
        )

        url = f'/api/v1/transformation/executions/{execution.id}/progress/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['progress_percentage'], 50.0)
        self.assertEqual(response.data['current_step'], "step1")

    def test_get_execution_progress_completed(self):
        """Test getting progress for completed execution."""
        from django.utils import timezone
        from datetime import timedelta

        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset,
            started_at=timezone.now() - timedelta(seconds=60),
            completed_at=timezone.now()
        )

        url = f'/api/v1/transformation/executions/{execution.id}/progress/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.COMPLETED)
        self.assertEqual(response.data['progress_percentage'], 100.0)

    def test_get_execution_result_success(self):
        """Test getting execution result for completed execution."""
        from django.utils import timezone
        from datetime import timedelta

        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset,
            started_at=timezone.now() - timedelta(seconds=60),
            completed_at=timezone.now(),
            metrics={"items_processed": 1000, "duration_seconds": 60.0}
        )

        url = f'/api/v1/transformation/executions/{execution.id}/result/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.COMPLETED)
        self.assertEqual(response.data['result_asset_id'], str(result_asset.id))
        self.assertIn('metrics', response.data)
        self.assertIn('execution_log', response.data)
        self.assertIn('duration_seconds', response.data)

    def test_get_execution_result_not_completed(self):
        """Test getting result for non-completed execution (should fail)."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING
        )

        url = f'/api/v1/transformation/executions/{execution.id}/result/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_get_execution_result_failed(self):
        """Test getting result for failed execution."""
        from django.utils import timezone
        from datetime import timedelta

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.FAILED,
            started_at=timezone.now() - timedelta(seconds=30),
            completed_at=timezone.now()
        )
        execution.add_log_entry("Test error message", "ERROR")

        url = f'/api/v1/transformation/executions/{execution.id}/result/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.FAILED)
        self.assertIsNotNone(response.data['error_message'])
        self.assertIn('execution_log', response.data)

    def test_get_execution_result_with_error_message(self):
        """Test getting result for failed execution with error message."""
        from django.utils import timezone
        from datetime import timedelta

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.FAILED,
            started_at=timezone.now() - timedelta(seconds=30),
            completed_at=timezone.now()
        )
        execution.add_log_entry("Test error message", "ERROR")

        url = f'/api/v1/transformation/executions/{execution.id}/result/'
        response = self.client.get(url)

        # get_result now works for both COMPLETED and FAILED (terminal states)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], ExecutionStatus.FAILED)
        self.assertIsNotNone(response.data['error_message'])
        self.assertEqual(response.data['error_message'], "Test error message")

    def test_execution_endpoints_tenant_isolation(self):
        """Test that execution endpoints enforce tenant isolation."""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE
        )

        # Create result asset for completed execution
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        # Create execution in first tenant
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset
        )

        # Try to access with other tenant's user
        self.client.force_authenticate(user=other_user)

        url = f'/api/v1/transformation/executions/{execution.id}/'
        response = self.client.get(url)

        # Should not be able to access
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_execution_endpoints_authentication_required(self):
        """Test that execution endpoints require authentication."""
        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset
        )

        # Unauthenticated request
        self.client.force_authenticate(user=None)

        url = f'/api/v1/transformation/executions/{execution.id}/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_executions_empty(self):
        """Test listing executions when none exist."""
        url = f'/api/v1/transformation/pipelines/{self.pipeline.id}/executions/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 0)
        self.assertEqual(len(response.data['results']), 0)

    def test_get_execution_progress_with_logs(self):
        """Test getting progress with execution logs."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.RUNNING
        )
        execution.add_log_entry("Step 1 started", "INFO")
        execution.add_log_entry("Step 1 completed", "INFO")
        execution.add_log_entry("Step 2 started", "INFO")

        url = f'/api/v1/transformation/executions/{execution.id}/progress/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('recent_logs', response.data)
        self.assertGreater(len(response.data['recent_logs']), 0)

    def test_get_execution_result_with_complete_data(self):
        """Test getting execution result with all data."""
        from django.utils import timezone
        from datetime import timedelta

        result_asset = Asset.objects.create(
            tenant=self.tenant,
            key="result-asset",
            name="Result Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user
        )

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=result_asset,
            started_at=timezone.now() - timedelta(seconds=120),
            completed_at=timezone.now()
        )
        execution.add_log_entry("Execution started", "INFO")
        execution.add_log_entry("Execution completed", "INFO")
        execution.update_metrics(
            items_processed=5000,
            duration_seconds=120.0,
            throughput_items_per_second=41.67
        )

        url = f'/api/v1/transformation/executions/{execution.id}/result/'
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['result_asset_id'], str(result_asset.id))
        self.assertEqual(response.data['result_asset_name'], result_asset.name)
        self.assertIn('items_processed', response.data['metrics'])
        self.assertGreater(len(response.data['execution_log']), 0)
        self.assertIsNotNone(response.data['duration_seconds'])

