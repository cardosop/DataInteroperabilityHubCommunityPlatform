"""
Unit tests for PipelineExecution model.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant
from hub.apps.transformation.models import (
    ExecutionMode,
    ExecutionStatus,
    PipelineExecution,
    PipelineStatus,
    TransformationPipeline,
)

User = get_user_model()


class PipelineExecutionModelTest(TestCase):
    """Test cases for PipelineExecution model."""

    def setUp(self):
        """Set up per-test fixtures."""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        self.valid_pipeline_definition = {
            "version": "1.0.0",
            "steps": [{"name": "step1", "type": "task", "task": "extract_data", "input": {}}],
        }
        self.pipeline = TransformationPipeline.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name=f"Test Pipeline {uuid.uuid4().hex[:8]}",
            pipeline_definition=self.valid_pipeline_definition,
            status=PipelineStatus.ACTIVE,
        )
        self.source_asset = Asset.objects.create(
            tenant=self.tenant, key="source-asset", name="Source Asset", status=AssetStatus.ACTIVE
        )
        self.result_asset = Asset.objects.create(
            tenant=self.tenant, key="result-asset", name="Result Asset", status=AssetStatus.ACTIVE
        )

    def test_create_execution(self):
        """Test creating a pipeline execution."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            execution_mode=ExecutionMode.MANUAL,
            status=ExecutionStatus.PENDING,
        )

        self.assertIsNotNone(execution.id)
        self.assertEqual(execution.pipeline, self.pipeline)
        self.assertEqual(execution.asset, self.source_asset)
        self.assertEqual(execution.execution_mode, ExecutionMode.MANUAL)
        self.assertEqual(execution.status, ExecutionStatus.PENDING)
        self.assertIsNone(execution.started_at)
        self.assertIsNone(execution.completed_at)
        self.assertIsNone(execution.result_asset)

    def test_execution_str_representation(self):
        """Test execution string representation."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.RUNNING
        )

        expected_str = f"Execution of {self.pipeline.name} on {self.source_asset.name} ({ExecutionStatus.RUNNING})"
        self.assertEqual(str(execution), expected_str)

    def test_execution_default_status(self):
        """Test execution defaults to PENDING status."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        self.assertEqual(execution.status, ExecutionStatus.PENDING)

    def test_execution_default_mode(self):
        """Test execution defaults to MANUAL mode."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        self.assertEqual(execution.execution_mode, ExecutionMode.MANUAL)

    def test_execution_default_log(self):
        """Test execution has default empty execution log."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        self.assertEqual(execution.execution_log, [])

    def test_execution_default_metrics(self):
        """Test execution has default empty metrics."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        self.assertEqual(execution.metrics, {})

    def test_execution_validation_invalid_log_not_list(self):
        """Test execution validation fails when log is not a list."""
        execution = PipelineExecution(
            pipeline=self.pipeline, asset=self.source_asset, execution_log="not a list"
        )

        with self.assertRaises(ValidationError):
            execution.full_clean()

    def test_execution_validation_invalid_metrics_not_dict(self):
        """Test execution validation fails when metrics is not a dict."""
        execution = PipelineExecution(
            pipeline=self.pipeline, asset=self.source_asset, metrics="not a dict"
        )

        with self.assertRaises(ValidationError):
            execution.full_clean()

    def test_execution_validation_completed_before_started(self):
        """Test execution validation fails when completed_at is before started_at."""
        now = timezone.now()
        execution = PipelineExecution(
            pipeline=self.pipeline,
            asset=self.source_asset,
            started_at=now,
            completed_at=now - timedelta(seconds=10),
        )

        with self.assertRaises(ValidationError):
            execution.full_clean()

    def test_execution_validation_completed_without_result_asset(self):
        """Test execution validation fails when completed without result_asset."""
        execution = PipelineExecution(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=None,
        )

        with self.assertRaises(ValidationError):
            execution.full_clean()

    def test_execution_is_pending(self):
        """Test is_pending method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.PENDING
        )

        self.assertTrue(execution.is_pending())
        execution.status = ExecutionStatus.RUNNING
        self.assertFalse(execution.is_pending())

    def test_execution_is_running(self):
        """Test is_running method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.RUNNING
        )

        self.assertTrue(execution.is_running())
        execution.status = ExecutionStatus.COMPLETED
        self.assertFalse(execution.is_running())

    def test_execution_is_completed(self):
        """Test is_completed method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=self.result_asset,
        )

        self.assertTrue(execution.is_completed())
        execution.status = ExecutionStatus.FAILED
        self.assertFalse(execution.is_completed())

    def test_execution_is_failed(self):
        """Test is_failed method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.FAILED
        )

        self.assertTrue(execution.is_failed())
        execution.status = ExecutionStatus.COMPLETED
        self.assertFalse(execution.is_failed())

    def test_execution_is_terminal(self):
        """Test is_terminal method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.COMPLETED,
            result_asset=self.result_asset,
        )

        self.assertTrue(execution.is_terminal())

        execution.status = ExecutionStatus.FAILED
        self.assertTrue(execution.is_terminal())

        execution.status = ExecutionStatus.CANCELLED
        self.assertTrue(execution.is_terminal())

        execution.status = ExecutionStatus.PENDING
        self.assertFalse(execution.is_terminal())

        execution.status = ExecutionStatus.RUNNING
        self.assertFalse(execution.is_terminal())

    def test_execution_can_cancel(self):
        """Test can_cancel method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.PENDING
        )

        self.assertTrue(execution.can_cancel())

        execution.status = ExecutionStatus.RUNNING
        self.assertTrue(execution.can_cancel())

        execution.status = ExecutionStatus.COMPLETED
        self.assertFalse(execution.can_cancel())

        execution.status = ExecutionStatus.FAILED
        self.assertFalse(execution.can_cancel())

    def test_execution_mark_started(self):
        """Test mark_started method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, status=ExecutionStatus.PENDING
        )

        execution.mark_started()

        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.RUNNING)
        self.assertIsNotNone(execution.started_at)

    def test_execution_mark_completed(self):
        """Test mark_completed method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        metrics = {"items_processed": 100, "duration_seconds": 5.5, "throughput": 18.18}

        execution.mark_completed(result_asset=self.result_asset, metrics=metrics)

        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(execution.result_asset, self.result_asset)
        self.assertEqual(execution.metrics["items_processed"], 100)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.COMPLETED)
        self.assertEqual(execution.result_asset, self.result_asset)

    def test_execution_mark_failed(self):
        """Test mark_failed method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        error_message = "Transformation failed: Invalid data format"
        execution.mark_failed(error_message=error_message)

        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertIsNotNone(execution.completed_at)
        self.assertEqual(len(execution.execution_log), 1)
        self.assertEqual(execution.execution_log[0]["level"], "ERROR")
        self.assertIn("Invalid data format", execution.execution_log[0]["message"])
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.FAILED)

    def test_execution_mark_failed_with_log_entry(self):
        """Test mark_failed with explicit log entry."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        log_entry = "Pipeline step failed: connection timeout"
        execution.mark_failed(execution_log_entry=log_entry)

        self.assertEqual(execution.status, ExecutionStatus.FAILED)
        self.assertEqual(len(execution.execution_log), 1)
        self.assertEqual(execution.execution_log[0]["message"], log_entry)

    def test_execution_mark_cancelled(self):
        """Test mark_cancelled method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            status=ExecutionStatus.RUNNING,
            started_at=timezone.now(),
        )

        execution.mark_cancelled()

        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)
        self.assertIsNotNone(execution.completed_at)
        execution.refresh_from_db()
        self.assertEqual(execution.status, ExecutionStatus.CANCELLED)

    def test_execution_add_log_entry(self):
        """Test add_log_entry method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        execution.add_log_entry("Pipeline started", "INFO")
        execution.add_log_entry("Processing data", "DEBUG")
        execution.add_log_entry("Warning: slow performance", "WARNING")

        self.assertEqual(len(execution.execution_log), 3)
        self.assertEqual(execution.execution_log[0]["level"], "INFO")
        self.assertEqual(execution.execution_log[0]["message"], "Pipeline started")
        self.assertEqual(execution.execution_log[1]["level"], "DEBUG")
        self.assertEqual(execution.execution_log[2]["level"], "WARNING")
        execution.refresh_from_db()
        self.assertEqual(len(execution.execution_log), 3)

    def test_execution_get_duration_seconds(self):
        """Test get_duration_seconds method."""
        started = timezone.now()
        completed = started + timedelta(seconds=10)

        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            started_at=started,
            completed_at=completed,
        )

        self.assertEqual(execution.get_duration_seconds(), 10.0)

        # Test with no completed_at
        execution.completed_at = None
        self.assertIsNone(execution.get_duration_seconds())

        # Test with no started_at
        execution.started_at = None
        self.assertIsNone(execution.get_duration_seconds())

    def test_execution_update_metrics(self):
        """Test update_metrics method."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        execution.update_metrics(items_processed=100, duration_seconds=5.5, throughput=18.18)

        self.assertEqual(execution.metrics["items_processed"], 100)
        self.assertEqual(execution.metrics["duration_seconds"], 5.5)
        self.assertEqual(execution.metrics["throughput"], 18.18)

        # Update existing metrics
        execution.update_metrics(items_processed=150)
        self.assertEqual(execution.metrics["items_processed"], 150)
        self.assertEqual(execution.metrics["duration_seconds"], 5.5)  # Should remain

        execution.refresh_from_db()
        self.assertEqual(execution.metrics["items_processed"], 150)

    def test_execution_log_can_store_multiple_entries(self):
        """Test execution log can store multiple log entries."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        log_entries = [
            {"timestamp": "2025-01-01T10:00:00Z", "level": "INFO", "message": "Started"},
            {"timestamp": "2025-01-01T10:00:05Z", "level": "INFO", "message": "Processing"},
            {"timestamp": "2025-01-01T10:00:10Z", "level": "INFO", "message": "Completed"},
        ]

        execution.execution_log = log_entries
        execution.save()

        self.assertEqual(len(execution.execution_log), 3)
        self.assertEqual(execution.execution_log[0]["message"], "Started")

    def test_execution_metrics_can_store_arbitrary_data(self):
        """Test metrics field can store arbitrary JSON data."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        metrics = {
            "duration_seconds": 10.5,
            "items_processed": 1000,
            "items_failed": 5,
            "throughput": 95.24,
            "memory_usage_mb": 512,
            "cpu_usage_percent": 75.5,
        }

        execution.metrics = metrics
        execution.save()

        self.assertEqual(execution.metrics, metrics)
        self.assertEqual(execution.metrics["duration_seconds"], 10.5)
        self.assertEqual(execution.metrics["items_processed"], 1000)

    def test_execution_created_at_auto_set(self):
        """Test created_at is automatically set."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        self.assertIsNotNone(execution.created_at)

    def test_execution_updated_at_auto_set(self):
        """Test updated_at is automatically set and updated."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        original_updated_at = execution.updated_at

        # Update execution
        execution.status = ExecutionStatus.RUNNING
        execution.save()

        execution.refresh_from_db()
        self.assertGreater(execution.updated_at, original_updated_at)

    def test_execution_ordering(self):
        """Test execution ordering by started_at and created_at."""
        now = timezone.now()
        # Create executions with different timestamps
        execution1 = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, started_at=now - timedelta(hours=3)
        )
        execution2 = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, started_at=now - timedelta(hours=2)
        )
        execution3 = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset, started_at=now - timedelta(hours=1)
        )

        # Query ordered by -started_at, -created_at (most recent first)
        executions = list(PipelineExecution.objects.all())

        # Most recent started_at should be first
        self.assertGreaterEqual(
            executions[0].started_at,
            executions[1].started_at,
        )
        self.assertGreaterEqual(
            executions[1].started_at,
            executions[2].started_at,
        )
        # Verify the expected descending order
        self.assertEqual(executions[0].id, execution3.id)
        self.assertEqual(executions[1].id, execution2.id)
        self.assertEqual(executions[2].id, execution1.id)

    def test_execution_foreign_key_to_pipeline(self):
        """Test foreign key relationship to TransformationPipeline."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        # Test reverse relationship
        self.assertIn(execution, self.pipeline.executions.all())

        # Test cascade delete
        self.pipeline.delete()

        # Execution should be deleted
        self.assertFalse(PipelineExecution.objects.filter(id=execution.id).exists())

    def test_execution_foreign_key_to_asset(self):
        """Test foreign key relationship to Asset."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline, asset=self.source_asset
        )

        # Test reverse relationship
        self.assertIn(execution, self.source_asset.transformation_executions.all())

        # Test cascade delete
        self.source_asset.delete()

        # Execution should be deleted
        self.assertFalse(PipelineExecution.objects.filter(id=execution.id).exists())

    def test_execution_foreign_key_to_result_asset(self):
        """Test foreign key relationship to result Asset."""
        execution = PipelineExecution.objects.create(
            pipeline=self.pipeline,
            asset=self.source_asset,
            result_asset=self.result_asset,
            status=ExecutionStatus.COMPLETED,
        )

        # Test reverse relationship
        self.assertIn(execution, self.result_asset.transformation_result_executions.all())

        # Test SET_NULL on delete
        self.result_asset.delete()

        execution.refresh_from_db()
        self.assertIsNone(execution.result_asset)
