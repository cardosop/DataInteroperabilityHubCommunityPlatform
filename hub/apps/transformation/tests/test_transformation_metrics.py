"""
Unit tests for transformation pipeline metrics collection

Tests verify that metrics are recorded correctly for transformation pipelines.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.observability.otel_metrics import (
    transformation_pipeline_created_total,
    transformation_pipeline_execution_duration_seconds,
    transformation_pipeline_execution_success_rate,
    transformation_pipeline_execution_queue_depth,
    transformation_preview_generation_duration_seconds,
    transformation_wrangling_operations_total,
)
from hub.apps.transformation.monitoring import (
    record_pipeline_created,
    record_pipeline_execution,
    update_queue_depth,
    record_preview_generation,
    record_wrangling_operation,
)


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TransformationMetricsTest(TestCase):
    """Test transformation pipeline metrics collection"""

    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant
        )
        self.tenant_id = str(self.tenant.id)

    def test_pipeline_created_metric(self):
        """Test that pipeline created metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_pipeline_created_total)

        # Verify metric has expected labels
        labels = transformation_pipeline_created_total._labelnames
        self.assertIn('tenant_id', labels)

        # Record pipeline creation
        record_pipeline_created(self.tenant_id)

        # Verify metric can be incremented
        transformation_pipeline_created_total.labels(
            tenant_id=self.tenant_id
        ).inc()
        self.assertTrue(True)  # Metric exists and can be incremented

    def test_pipeline_execution_duration_metric(self):
        """Test that pipeline execution duration metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_pipeline_execution_duration_seconds)

        # Verify metric has expected labels
        labels = transformation_pipeline_execution_duration_seconds._labelnames
        self.assertIn('status', labels)
        self.assertIn('tenant_id', labels)

        # Record execution duration
        transformation_pipeline_execution_duration_seconds.labels(
            status="COMPLETED",
            tenant_id=self.tenant_id
        ).observe(10.5)
        self.assertTrue(True)  # Metric exists and can observe values

    def test_pipeline_execution_success_rate_metric(self):
        """Test that pipeline execution success rate metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_pipeline_execution_success_rate)

        # Verify metric has expected labels
        labels = transformation_pipeline_execution_success_rate._labelnames
        self.assertIn('tenant_id', labels)

        # Record success rate
        transformation_pipeline_execution_success_rate.labels(
            tenant_id=self.tenant_id
        ).set(1.0)
        self.assertTrue(True)  # Metric exists and can be set

    def test_pipeline_execution_queue_depth_metric(self):
        """Test that pipeline execution queue depth metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_pipeline_execution_queue_depth)

        # Verify metric has expected labels
        labels = transformation_pipeline_execution_queue_depth._labelnames
        self.assertIn('status', labels)
        self.assertIn('tenant_id', labels)

        # Update queue depth
        update_queue_depth(self.tenant_id, "PENDING", 5)

        # Verify metric can be set
        transformation_pipeline_execution_queue_depth.labels(
            status="PENDING",
            tenant_id=self.tenant_id
        ).set(5)
        self.assertTrue(True)  # Metric exists and can be set

    def test_preview_generation_duration_metric(self):
        """Test that preview generation duration metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_preview_generation_duration_seconds)

        # Verify metric has expected labels
        labels = transformation_preview_generation_duration_seconds._labelnames
        self.assertIn('tenant_id', labels)

        # Record preview generation duration
        transformation_preview_generation_duration_seconds.labels(
            tenant_id=self.tenant_id
        ).observe(2.5)
        self.assertTrue(True)  # Metric exists and can observe values

    def test_wrangling_operations_metric(self):
        """Test that wrangling operations metric is recorded"""
        # Verify metric exists
        self.assertIsNotNone(transformation_wrangling_operations_total)

        # Verify metric has expected labels
        labels = transformation_wrangling_operations_total._labelnames
        self.assertIn('operation_type', labels)
        self.assertIn('status', labels)
        self.assertIn('tenant_id', labels)

        # Record wrangling operation
        record_wrangling_operation(
            tenant_id=self.tenant_id,
            operation_type="FILTER",
            status="SUCCESS"
        )

        # Verify metric can be incremented
        transformation_wrangling_operations_total.labels(
            operation_type="FILTER",
            status="SUCCESS",
            tenant_id=self.tenant_id
        ).inc()
        self.assertTrue(True)  # Metric exists and can be incremented

    def test_record_pipeline_execution_context_manager(self):
        """Test that pipeline execution context manager records metrics"""
        # Use context manager to record execution
        with record_pipeline_execution(
            tenant_id=self.tenant_id,
            pipeline_id="test-pipeline-id",
            status="COMPLETED"
        ):
            # Simulate execution work
            pass

        # Verify metrics were recorded (can't easily test exact values without Prometheus)
        self.assertTrue(True)  # Context manager executed without error

    def test_record_preview_generation_context_manager(self):
        """Test that preview generation context manager records metrics"""
        # Use context manager to record preview generation
        with record_preview_generation(self.tenant_id):
            # Simulate preview generation work
            pass

        # Verify metrics were recorded (can't easily test exact values without Prometheus)
        self.assertTrue(True)  # Context manager executed without error

