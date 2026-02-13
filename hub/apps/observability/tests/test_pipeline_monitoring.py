"""
Unit tests for Pipeline Monitoring service.
"""

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.observability.models import PipelineExecution
from hub.apps.observability.pipeline_monitoring import PipelineMonitor
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class PipelineMonitorTest(TestCase):
    """Test Pipeline Monitoring service"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", kyc_status=KYCStatus.VERIFIED
        )

    def test_record_execution(self):
        """Test recording a pipeline execution"""
        execution = PipelineMonitor.record_execution(
            tenant_id=str(self.tenant.id),
            pipeline_type="SCHEDULED_INGESTION",
            pipeline_id="123e4567-e89b-12d3-a456-426614174000",
            pipeline_name="Test Pipeline",
            status="COMPLETED",
            started_at=timezone.now() - timedelta(seconds=60),
            completed_at=timezone.now(),
            execution_time_seconds=60.0,
            items_processed=100,
            items_failed=0,
        )

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.pipeline_type, "SCHEDULED_INGESTION")
        self.assertEqual(execution.status, "COMPLETED")
        self.assertEqual(execution.items_processed, 100)
        self.assertEqual(execution.items_failed, 0)

    def test_update_execution(self):
        """Test updating a pipeline execution"""
        execution = PipelineMonitor.record_execution(
            tenant_id=str(self.tenant.id),
            pipeline_type="DQ_RUN",
            pipeline_id="123e4567-e89b-12d3-a456-426614174001",
            status="RUNNING",
        )

        updated = PipelineMonitor.update_execution(
            execution_id=str(execution.id),
            status="COMPLETED",
            completed_at=timezone.now(),
            execution_time_seconds=30.0,
            items_processed=50,
        )

        self.assertEqual(updated.status, "COMPLETED")
        self.assertEqual(updated.execution_time_seconds, 30.0)
        self.assertEqual(updated.items_processed, 50)

    def test_get_pipeline_dashboard(self):
        """Test getting pipeline dashboard"""
        # Create some executions
        for i in range(5):
            PipelineMonitor.record_execution(
                tenant_id=str(self.tenant.id),
                pipeline_type="SCHEDULED_INGESTION",
                pipeline_id=f"123e4567-e89b-12d3-a456-42661417400{i}",
                status="COMPLETED" if i < 4 else "FAILED",
                started_at=timezone.now() - timedelta(seconds=60),
                completed_at=timezone.now(),
                execution_time_seconds=60.0,
                items_processed=100,
                items_failed=0 if i < 4 else 10,
            )

        dashboard = PipelineMonitor.get_pipeline_dashboard(tenant_id=str(self.tenant.id), limit=10)

        self.assertIn("results", dashboard)
        self.assertIn("summary", dashboard)
        self.assertEqual(len(dashboard["results"]), 5)
        self.assertEqual(dashboard["summary"]["total_executions"], 5)
        self.assertEqual(dashboard["summary"]["completed_executions"], 4)
        self.assertEqual(dashboard["summary"]["failed_executions"], 1)
        self.assertGreater(dashboard["summary"]["success_rate_percent"], 0)

    def test_get_pipeline_dashboard_with_filters(self):
        """Test getting pipeline dashboard with filters"""
        # Create executions of different types
        PipelineMonitor.record_execution(
            tenant_id=str(self.tenant.id),
            pipeline_type="SCHEDULED_INGESTION",
            pipeline_id="123e4567-e89b-12d3-a456-426614174010",
            status="COMPLETED",
        )

        PipelineMonitor.record_execution(
            tenant_id=str(self.tenant.id),
            pipeline_type="DQ_RUN",
            pipeline_id="123e4567-e89b-12d3-a456-426614174011",
            status="COMPLETED",
        )

        # Filter by pipeline type
        dashboard = PipelineMonitor.get_pipeline_dashboard(
            tenant_id=str(self.tenant.id), pipeline_type="SCHEDULED_INGESTION", limit=10
        )

        self.assertEqual(len(dashboard["results"]), 1)
        self.assertEqual(dashboard["results"][0]["pipeline_type"], "SCHEDULED_INGESTION")

    def test_sync_from_jobs(self):
        """Test syncing pipeline executions from Job records"""
        # Create a job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.COMPLETED,
            resource_type="ASSET",
            resource_id="123e4567-e89b-12d3-a456-426614174020",
            started_at=timezone.now() - timedelta(seconds=30),
            completed_at=timezone.now(),
        )

        # Sync from jobs
        count = PipelineMonitor.sync_from_jobs(tenant_id=str(self.tenant.id), limit=100)

        self.assertGreater(count, 0)

        # Check that execution was created
        execution = PipelineExecution.objects.filter(
            tenant=self.tenant, pipeline_type="DQ_RUN", pipeline_id=str(job.id)
        ).first()

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, "COMPLETED")
