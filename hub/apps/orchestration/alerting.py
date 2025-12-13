"""
Workflow Alerting Service

Provides alerting capabilities for workflow monitoring including:
- Workflow timeout detection
- Failure rate monitoring
- Retry exhaustion detection
- Stuck workflow detection
- Step failure rate monitoring
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.db import transaction

from .models import WorkflowInstance, WorkflowStep, WorkflowStatus, StepStatus

logger = logging.getLogger(__name__)


class WorkflowAlerting:
    """
    Workflow alerting service for monitoring workflow health.
    
    Provides methods to check for various alert conditions and send alerts.
    """
    
    def check_workflow_timeouts(
        self,
        timeout_threshold_seconds: int = 3600,
        workflow_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for workflow instances that have exceeded timeout threshold.
        
        Args:
            timeout_threshold_seconds: Timeout threshold in seconds (default: 3600 = 1 hour)
            workflow_name: Optional workflow name filter
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        threshold_time = timezone.now() - timedelta(seconds=timeout_threshold_seconds)
        
        query = Q(
            status=WorkflowStatus.RUNNING,
            started_at__lt=threshold_time
        )
        
        if workflow_name:
            query &= Q(workflow_name=workflow_name)
        
        timed_out_workflows = WorkflowInstance.objects.filter(query).select_related('workflow_definition')
        
        for instance in timed_out_workflows:
            # Check if workflow has a custom timeout
            workflow_timeout = None
            if instance.workflow_definition and instance.workflow_definition.dsl_json:
                workflow_timeout = instance.workflow_definition.dsl_json.get('timeout_seconds')
            
            effective_timeout = workflow_timeout if workflow_timeout else timeout_threshold_seconds
            
            # Re-check with effective timeout
            effective_threshold = timezone.now() - timedelta(seconds=effective_timeout)
            if instance.started_at < effective_threshold:
                alert = {
                    "alert_type": "workflow_timeout",
                    "severity": "high",
                    "workflow_instance_id": str(instance.id),
                    "workflow_name": instance.workflow_name,
                    "workflow_version": instance.workflow_version,
                    "started_at": instance.started_at.isoformat(),
                    "timeout_threshold": effective_timeout,
                    "message": f"Workflow {instance.workflow_name} (instance {instance.id}) has exceeded timeout threshold of {effective_timeout} seconds"
                }
                alerts.append(alert)
                self.send_alert(alert)
        
        return alerts
    
    def check_failed_workflows(
        self,
        min_failure_count: int = 5,
        time_window_minutes: int = 15,
        workflow_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for high failure rates in a time window.
        
        Args:
            min_failure_count: Minimum number of failures to trigger alert
            time_window_minutes: Time window in minutes (default: 15)
            workflow_name: Optional workflow name filter
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        window_start = timezone.now() - timedelta(minutes=time_window_minutes)
        
        query = Q(
            status=WorkflowStatus.FAILED,
            completed_at__gte=window_start
        )
        
        if workflow_name:
            query &= Q(workflow_name=workflow_name)
        
        # Group by workflow_name and count failures
        failure_counts = (
            WorkflowInstance.objects
            .filter(query)
            .values('workflow_name', 'workflow_version')
            .annotate(failure_count=Count('id'))
            .filter(failure_count__gte=min_failure_count)
        )
        
        for failure_info in failure_counts:
            alert = {
                "alert_type": "workflow_failure_rate",
                "severity": "high",
                "workflow_name": failure_info['workflow_name'],
                "workflow_version": failure_info['workflow_version'],
                "failure_count": failure_info['failure_count'],
                "time_window_minutes": time_window_minutes,
                "message": f"Workflow {failure_info['workflow_name']} has {failure_info['failure_count']} failures in the last {time_window_minutes} minutes"
            }
            alerts.append(alert)
            self.send_alert(alert)
        
        return alerts
    
    def check_retry_exhaustion(self) -> List[Dict[str, Any]]:
        """
        Check for workflow instances that have exhausted all retry attempts.
        
        Returns:
            List of alert dictionaries
        """
        alerts = []
        
        # Find workflows that are failed and have reached max retries
        exhausted_workflows = WorkflowInstance.objects.filter(
            status=WorkflowStatus.FAILED,
            retry_count__gte=1  # Has been retried at least once
        ).select_related('workflow_definition')
        
        for instance in exhausted_workflows:
            # Get max retries from instance or workflow definition or default
            max_retries = instance.max_retries if instance.max_retries else 3  # Default
            if max_retries == 3 and instance.workflow_definition and instance.workflow_definition.dsl_json:
                max_retries = instance.workflow_definition.dsl_json.get('max_retries', max_retries)
            
            if instance.retry_count >= max_retries:
                error_message = "Unknown error"
                if instance.error_details:
                    error_message = instance.error_details.get('error_message', error_message)
                
                alert = {
                    "alert_type": "workflow_retry_exhaustion",
                    "severity": "critical",
                    "workflow_instance_id": str(instance.id),
                    "workflow_name": instance.workflow_name,
                    "workflow_version": instance.workflow_version,
                    "retry_count": instance.retry_count,
                    "max_retries": max_retries,
                    "error_message": error_message,
                    "failed_at": instance.completed_at.isoformat() if instance.completed_at else None,
                    "message": f"Workflow {instance.workflow_name} (instance {instance.id}) has exhausted all {max_retries} retry attempts"
                }
                alerts.append(alert)
                self.send_alert(alert)
        
        return alerts
    
    def check_stuck_workflows(
        self,
        stuck_threshold_minutes: int = 30,
        workflow_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for workflow instances that appear stuck (no progress for threshold time).
        
        Args:
            stuck_threshold_minutes: Threshold in minutes (default: 30)
            workflow_name: Optional workflow name filter
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        threshold_time = timezone.now() - timedelta(minutes=stuck_threshold_minutes)
        
        query = Q(
            status=WorkflowStatus.RUNNING,
            updated_at__lt=threshold_time
        )
        
        if workflow_name:
            query &= Q(workflow_name=workflow_name)
        
        stuck_workflows = WorkflowInstance.objects.filter(query).select_related('workflow_definition')
        
        for instance in stuck_workflows:
            # Get current step
            current_step = instance.steps.filter(step_index=instance.current_step_index).first()
            
            stuck_step_name = "unknown"
            stuck_step_index = instance.current_step_index
            step_started_at = None
            
            if current_step:
                stuck_step_name = current_step.step_name
                step_started_at = current_step.started_at.isoformat() if current_step.started_at else None
            
            alert = {
                "alert_type": "workflow_stuck",
                "severity": "medium",
                "workflow_instance_id": str(instance.id),
                "workflow_name": instance.workflow_name,
                "workflow_version": instance.workflow_version,
                "stuck_step_name": stuck_step_name,
                "stuck_step_index": stuck_step_index,
                "step_started_at": step_started_at,
                "last_updated_at": instance.updated_at.isoformat(),
                "stuck_threshold_minutes": stuck_threshold_minutes,
                "message": f"Workflow {instance.workflow_name} (instance {instance.id}) appears stuck at step {stuck_step_name} for {stuck_threshold_minutes} minutes"
            }
            alerts.append(alert)
            self.send_alert(alert)
        
        return alerts
    
    def check_step_failure_rate(
        self,
        min_failure_rate: float = 0.5,
        min_failures: int = 10,
        time_window_minutes: int = 60,
        workflow_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Check for high failure rates for specific workflow steps.
        
        Args:
            min_failure_rate: Minimum failure rate to trigger alert (0.0-1.0)
            min_failures: Minimum number of failures required
            time_window_minutes: Time window in minutes (default: 60)
            workflow_name: Optional workflow name filter
            
        Returns:
            List of alert dictionaries
        """
        alerts = []
        window_start = timezone.now() - timedelta(minutes=time_window_minutes)
        
        query = Q(
            status=StepStatus.FAILED,
            completed_at__gte=window_start
        )
        
        if workflow_name:
            query &= Q(workflow_instance__workflow_name=workflow_name)
        
        # Group by workflow_name and step_name, count failures and total attempts
        step_stats = (
            WorkflowStep.objects
            .filter(query)
            .values('workflow_instance__workflow_name', 'workflow_instance__workflow_version', 'step_name')
            .annotate(
                failure_count=Count('id')
            )
        )
        
        # Get total attempts for same steps
        for step_stat in step_stats:
            if step_stat['failure_count'] < min_failures:
                continue
            
            # Get total attempts (completed + failed) for this step
            total_query = Q(
                workflow_instance__workflow_name=step_stat['workflow_instance__workflow_name'],
                step_name=step_stat['step_name'],
                started_at__gte=window_start
            )
            
            total_attempts = WorkflowStep.objects.filter(total_query).count()
            
            if total_attempts == 0:
                continue
            
            failure_rate = step_stat['failure_count'] / total_attempts
            
            if failure_rate >= min_failure_rate:
                alert = {
                    "alert_type": "step_failure_rate",
                    "severity": "high",
                    "workflow_name": step_stat['workflow_instance__workflow_name'],
                    "workflow_version": step_stat['workflow_instance__workflow_version'],
                    "step_name": step_stat['step_name'],
                    "failure_count": step_stat['failure_count'],
                    "total_attempts": total_attempts,
                    "failure_rate": failure_rate,
                    "time_window_minutes": time_window_minutes,
                    "message": f"Step {step_stat['step_name']} in workflow {step_stat['workflow_instance__workflow_name']} has failure rate of {failure_rate:.2%} ({step_stat['failure_count']}/{total_attempts})"
                }
                alerts.append(alert)
                self.send_alert(alert)
        
        return alerts
    
    def check_all_alerts(
        self,
        timeout_threshold_seconds: int = 3600,
        failure_rate_window_minutes: int = 15,
        stuck_threshold_minutes: int = 30,
        step_failure_rate_window_minutes: int = 60
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Check all alert conditions and return grouped alerts.
        
        Args:
            timeout_threshold_seconds: Timeout threshold for workflows
            failure_rate_window_minutes: Time window for failure rate checks
            stuck_threshold_minutes: Threshold for stuck workflow detection
            step_failure_rate_window_minutes: Time window for step failure rate checks
            
        Returns:
            Dictionary with alert types as keys and lists of alerts as values
        """
        all_alerts = {
            "timeouts": self.check_workflow_timeouts(timeout_threshold_seconds),
            "failures": self.check_failed_workflows(
                time_window_minutes=failure_rate_window_minutes
            ),
            "retry_exhaustion": self.check_retry_exhaustion(),
            "stuck": self.check_stuck_workflows(stuck_threshold_minutes),
            "step_failures": self.check_step_failure_rate(
                time_window_minutes=step_failure_rate_window_minutes
            )
        }
        
        return all_alerts
    
    def send_alert(self, alert: Dict[str, Any]) -> bool:
        """
        Send alert to logging system.
        
        Currently logs alerts. Can be extended to send to external systems
        (PagerDuty, Slack, Email, Prometheus Alertmanager, etc.).
        
        Args:
            alert: Alert dictionary
            
        Returns:
            True if alert was sent successfully
        """
        severity = alert.get('severity', 'medium')
        alert_type = alert.get('alert_type', 'unknown')
        message = alert.get('message', 'Workflow alert')
        
        # Log alert based on severity
        if severity == 'critical':
            logger.critical(f"Workflow alert [{alert_type}]: {message}", extra={"alert": alert})
        elif severity == 'high':
            logger.error(f"Workflow alert [{alert_type}]: {message}", extra={"alert": alert})
        elif severity == 'medium':
            logger.warning(f"Workflow alert [{alert_type}]: {message}", extra={"alert": alert})
        else:
            logger.info(f"Workflow alert [{alert_type}]: {message}", extra={"alert": alert})
        
        # TODO: Integrate with external alerting systems:
        # - PagerDuty Events API
        # - Slack Webhook API
        # - Email via Django email backend
        # - Prometheus Alertmanager
        
        return True
