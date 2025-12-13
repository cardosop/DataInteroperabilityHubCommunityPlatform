"""
Unit tests for workflow orchestration alerting.
"""
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta

from hub.apps.orchestration.alerting import WorkflowAlerting
from hub.apps.orchestration.models import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStep,
    WorkflowStatus,
    StepStatus
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class WorkflowAlertingTest(TestCase):
    """Test workflow alerting logic"""
    
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
        
        self.alerting = WorkflowAlerting()
    
    def test_check_workflow_timeouts_no_timeouts(self):
        """Test checking for timeouts when none exist"""
        # Create a recent workflow instance
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now()
        )
        
        alerts = self.alerting.check_workflow_timeouts(timeout_threshold_seconds=3600)
        self.assertEqual(len(alerts), 0)
    
    def test_check_workflow_timeouts_with_timeout(self):
        """Test checking for timeouts when one exists"""
        # Create an old running workflow instance
        old_time = timezone.now() - timedelta(hours=2)
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=old_time
        )
        
        alerts = self.alerting.check_workflow_timeouts(timeout_threshold_seconds=3600)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "workflow_timeout")
        self.assertEqual(alerts[0]["workflow_instance_id"], str(instance.id))
    
    def test_check_failed_workflows_no_failures(self):
        """Test checking for failed workflows when none exist"""
        alerts = self.alerting.check_failed_workflows(min_failure_count=5)
        self.assertEqual(len(alerts), 0)
    
    def test_check_failed_workflows_with_failures(self):
        """Test checking for failed workflows when failures exist"""
        # Create multiple failed workflow instances
        for i in range(6):
            WorkflowInstance.objects.create(
                workflow_definition=self.workflow_def,
                workflow_name="test_workflow",
                workflow_version="1.0.0",
                tenant=self.tenant,
                status=WorkflowStatus.FAILED,
                completed_at=timezone.now(),
                error_message="Test error"
            )
        
        alerts = self.alerting.check_failed_workflows(
            min_failure_count=5,
            time_window_minutes=60
        )
        self.assertGreater(len(alerts), 0)
        self.assertEqual(alerts[0]["alert_type"], "workflow_failure_rate")
    
    def test_check_retry_exhaustion_no_exhaustion(self):
        """Test checking for retry exhaustion when none exists"""
        # Create a failed workflow that hasn't exhausted retries
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=2,
            max_retries=3
        )
        
        alerts = self.alerting.check_retry_exhaustion()
        self.assertEqual(len(alerts), 0)
    
    def test_check_retry_exhaustion_with_exhaustion(self):
        """Test checking for retry exhaustion when one exists"""
        # Create a failed workflow that has exhausted retries
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=3,
            max_retries=3,
            error_message="Test error"
        )
        
        alerts = self.alerting.check_retry_exhaustion()
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "workflow_retry_exhaustion")
        self.assertEqual(alerts[0]["workflow_instance_id"], str(instance.id))
    
    def test_check_stuck_workflows_no_stuck(self):
        """Test checking for stuck workflows when none exist"""
        # Create a recent running workflow
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=timezone.now()
        )
        
        alerts = self.alerting.check_stuck_workflows(stuck_threshold_minutes=30)
        self.assertEqual(len(alerts), 0)
    
    def test_check_stuck_workflows_with_stuck(self):
        """Test checking for stuck workflows when one exists"""
        # Create an old running workflow with a stuck step
        old_time = timezone.now() - timedelta(hours=1)
        instance = WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=old_time
        )
        
        # Create a stuck step first
        step = WorkflowStep.objects.create(
            workflow_instance=instance,
            step_index=0,
            step_name="step1",
            step_type="task",
            status=StepStatus.RUNNING,
            started_at=old_time
        )
        
        # Manually update updated_at to bypass auto_now (after step creation)
        # This ensures the instance appears stuck even after step creation
        WorkflowInstance.objects.filter(id=instance.id).update(updated_at=old_time)
        # Also ensure step's started_at is set correctly
        WorkflowStep.objects.filter(id=step.id).update(started_at=old_time)
        
        # Refresh to get latest state
        instance.refresh_from_db()
        step.refresh_from_db()
        
        alerts = self.alerting.check_stuck_workflows(stuck_threshold_minutes=30)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0]["alert_type"], "workflow_stuck")
        self.assertEqual(alerts[0]["workflow_instance_id"], str(instance.id))
    
    def test_send_alert_success(self):
        """Test sending an alert successfully"""
        alert = {
            "alert_type": "test_alert",
            "severity": "high",
            "message": "Test alert message",
            "timestamp": timezone.now().isoformat()
        }
        
        with patch('hub.apps.orchestration.alerting.logger') as mock_logger:
            result = self.alerting.send_alert(alert)
            self.assertTrue(result)
            mock_logger.warning.assert_called_once()
    
    def test_send_alert_failure(self):
        """Test sending an alert with failure"""
        alert = {
            "alert_type": "test_alert",
            "severity": "high",
            "message": "Test alert message",
            "timestamp": timezone.now().isoformat()
        }
        
        with patch('hub.apps.orchestration.alerting.logger') as mock_logger:
            mock_logger.warning.side_effect = Exception("Test error")
            result = self.alerting.send_alert(alert)
            self.assertFalse(result)
            mock_logger.error.assert_called_once()
    
    def test_check_all_alerts(self):
        """Test checking all alert conditions"""
        # Create conditions for various alerts
        # Timeout
        old_time = timezone.now() - timedelta(hours=2)
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.RUNNING,
            started_at=old_time
        )
        
        # Retry exhaustion
        WorkflowInstance.objects.create(
            workflow_definition=self.workflow_def,
            workflow_name="test_workflow",
            workflow_version="1.0.0",
            tenant=self.tenant,
            status=WorkflowStatus.FAILED,
            retry_count=3,
            max_retries=3
        )
        
        with patch.object(self.alerting, 'send_alert') as mock_send:
            alerts = self.alerting.check_all_alerts()
            # Should have at least timeout and retry exhaustion alerts
            self.assertGreater(len(alerts), 0)
            # Verify send_alert was called for each alert
            self.assertEqual(mock_send.call_count, len(alerts))

