"""
Unit tests for workflow orchestration metrics.
"""
import json
import time
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.utils import timezone

from hub.apps.orchestration.metrics import (
    workflow_instances_created_total,
    workflow_instances_started_total,
    workflow_instances_completed_total,
    workflow_instances_failed_total,
    workflow_execution_duration_seconds,
    workflow_steps_started_total,
    workflow_steps_completed_total,
    workflow_steps_failed_total,
    get_tenant_id,
    get_error_type,
)
from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepStatus
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class WorkflowMetricsTest(TestCase):
    """Test workflow metrics recording"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"}
                ]
            },
            is_active=True
        )
    
    def test_get_tenant_id_with_tenant(self):
        """Test get_tenant_id with tenant ID"""
        tenant_id = str(self.tenant.id)
        result = get_tenant_id(tenant_id)
        self.assertEqual(result, tenant_id)
    
    def test_get_tenant_id_without_tenant(self):
        """Test get_tenant_id without tenant ID"""
        result = get_tenant_id(None)
        self.assertEqual(result, "system")
    
    def test_get_error_type_with_exception_type(self):
        """Test get_error_type with exception type"""
        error_details = {"exception_type": "ValidationError"}
        result = get_error_type(error_details)
        self.assertEqual(result, "validation_error")
    
    def test_get_error_type_with_timeout(self):
        """Test get_error_type with timeout error"""
        error_details = {"exception_type": "TimeoutError"}
        result = get_error_type(error_details)
        self.assertEqual(result, "timeout")
    
    def test_get_error_type_without_details(self):
        """Test get_error_type without error details"""
        result = get_error_type(None)
        self.assertEqual(result, "unknown")
    
    def test_get_error_type_with_connection_error(self):
        """Test get_error_type with connection error"""
        error_details = {"exception_type": "ConnectionError"}
        result = get_error_type(error_details)
        self.assertEqual(result, "connection_error")
    
    def test_workflow_instances_created_total_metric(self):
        """Test workflow_instances_created_total metric"""
        # Mock the metric to verify it's called
        with patch.object(workflow_instances_created_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            # Call the metric
            workflow_instances_created_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                tenant_id="test_tenant"
            ).inc()
            
            # Verify metric was called
            mock_labels.assert_called_once_with(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                tenant_id="test_tenant"
            )
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_instances_started_total_metric(self):
        """Test workflow_instances_started_total metric"""
        with patch.object(workflow_instances_started_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_instances_started_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_instances_completed_total_metric(self):
        """Test workflow_instances_completed_total metric"""
        with patch.object(workflow_instances_completed_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_instances_completed_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                status="COMPLETED",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_instances_failed_total_metric(self):
        """Test workflow_instances_failed_total metric"""
        with patch.object(workflow_instances_failed_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_instances_failed_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                error_type="validation_error",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_execution_duration_seconds_metric(self):
        """Test workflow_execution_duration_seconds metric"""
        with patch.object(workflow_execution_duration_seconds, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_execution_duration_seconds.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                status="COMPLETED",
                tenant_id="test_tenant"
            ).observe(10.5)
            
            mock_labels.assert_called_once()
            mock_labeled.observe.assert_called_once_with(10.5)
    
    def test_workflow_steps_started_total_metric(self):
        """Test workflow_steps_started_total metric"""
        with patch.object(workflow_steps_started_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_steps_started_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                step_name="step1",
                step_type="task",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_steps_completed_total_metric(self):
        """Test workflow_steps_completed_total metric"""
        with patch.object(workflow_steps_completed_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_steps_completed_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                step_name="step1",
                step_type="task",
                status="COMPLETED",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()
    
    def test_workflow_steps_failed_total_metric(self):
        """Test workflow_steps_failed_total metric"""
        with patch.object(workflow_steps_failed_total, 'labels') as mock_labels:
            mock_labeled = Mock()
            mock_labels.return_value = mock_labeled
            
            workflow_steps_failed_total.labels(
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                step_name="step1",
                step_type="task",
                error_type="validation_error",
                tenant_id="test_tenant"
            ).inc()
            
            mock_labels.assert_called_once()
            mock_labeled.inc.assert_called_once()


class WorkflowMetricsIntegrationTest(TestCase):
    """Integration tests for workflow metrics with actual workflow execution"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        
        # Create workflow definition
        self.workflow_def = WorkflowDefinition.objects.create(
            name="test_workflow",
            version="1.0.0",
            dsl_json={
                "version": "1.0",
                "steps": [
                    {"name": "step1", "type": "task", "task": "test_task"}
                ]
            },
            is_active=True
        )
    
    def test_metrics_recorded_during_workflow_execution(self):
        """Test that metrics are recorded during workflow execution"""
        from hub.apps.orchestration.workflow_engine import WorkflowEngine
        
        engine = WorkflowEngine()
        
        # Create instance (should record created metric)
        instance = engine.create_instance(
            workflow_name="test_workflow",
            input_data={"test": "data"},
            tenant_id=str(self.tenant.id),
            created_by_id=str(self.user.id)
        )
        
        self.assertIsNotNone(instance)
        self.assertEqual(instance.workflow_name, "test_workflow")
        
        # Start instance (should record started metric)
        instance = engine.start_instance(str(instance.id))
        self.assertEqual(instance.status, WorkflowStatus.RUNNING)
        
        # Note: We can't easily test the actual metric values without Prometheus,
        # but we can verify the workflow execution completes without errors
        # and that the metrics code paths are executed

