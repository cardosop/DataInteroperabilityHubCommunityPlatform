"""
Workflow Orchestration Metrics

Prometheus metrics for workflow execution monitoring and observability.
Tracks workflow instances, steps, execution times, failures, retries, and timeouts.
"""
from typing import Optional, Dict, Any
from django.conf import settings

from hub.apps.observability.otel_metrics import (
    _CounterWrapper,
    _HistogramWrapper,
    _UpDownCounterWrapper,
)


# ============================================================================
# Workflow Instance Metrics
# ============================================================================

# Workflow instance lifecycle metrics
workflow_instances_created_total = _CounterWrapper(
    'workflow_instances_created_total',
    'Total number of workflow instances created',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

workflow_instances_started_total = _CounterWrapper(
    'workflow_instances_started_total',
    'Total number of workflow instances started',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

workflow_instances_completed_total = _CounterWrapper(
    'workflow_instances_completed_total',
    'Total number of workflow instances completed',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'status', 'tenant_id')
)

workflow_instances_failed_total = _CounterWrapper(
    'workflow_instances_failed_total',
    'Total number of workflow instances failed',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'error_type', 'tenant_id')
)

workflow_instances_cancelled_total = _CounterWrapper(
    'workflow_instances_cancelled_total',
    'Total number of workflow instances cancelled',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

workflow_instances_retried_total = _CounterWrapper(
    'workflow_instances_retried_total',
    'Total number of workflow instance retries',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'retry_count', 'tenant_id')
)

# Workflow execution duration histogram
workflow_execution_duration_seconds = _HistogramWrapper(
    'workflow_execution_duration_seconds',
    'Workflow execution duration in seconds',
    unit='s',
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0, 7200.0),
    expected_labels=('workflow_name', 'workflow_version', 'status', 'tenant_id')
)

# Workflow timeout metrics
workflow_instances_timed_out_total = _CounterWrapper(
    'workflow_instances_timed_out_total',
    'Total number of workflow instances that timed out',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

# Current workflow instance counts (gauges)
workflow_instances_running = _UpDownCounterWrapper(
    'workflow_instances_running',
    'Current number of running workflow instances',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

workflow_instances_pending = _UpDownCounterWrapper(
    'workflow_instances_pending',
    'Current number of pending workflow instances',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

workflow_instances_failed_current = _UpDownCounterWrapper(
    'workflow_instances_failed_current',
    'Current number of failed workflow instances (not yet retried or cleaned up)',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)


# ============================================================================
# Workflow Step Metrics
# ============================================================================

# Workflow step lifecycle metrics
workflow_steps_started_total = _CounterWrapper(
    'workflow_steps_started_total',
    'Total number of workflow steps started',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'step_name', 'step_type', 'tenant_id')
)

workflow_steps_completed_total = _CounterWrapper(
    'workflow_steps_completed_total',
    'Total number of workflow steps completed',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'step_name', 'step_type', 'status', 'tenant_id')
)

workflow_steps_failed_total = _CounterWrapper(
    'workflow_steps_failed_total',
    'Total number of workflow steps failed',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'step_name', 'step_type', 'error_type', 'tenant_id')
)

workflow_steps_retried_total = _CounterWrapper(
    'workflow_steps_retried_total',
    'Total number of workflow step retries',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'step_name', 'step_type', 'retry_count', 'tenant_id')
)

# Workflow step execution duration histogram
workflow_step_execution_duration_seconds = _HistogramWrapper(
    'workflow_step_execution_duration_seconds',
    'Workflow step execution duration in seconds',
    unit='s',
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0),
    expected_labels=('workflow_name', 'workflow_version', 'step_name', 'step_type', 'status', 'tenant_id')
)


# ============================================================================
# Workflow Compensation/Rollback Metrics
# ============================================================================

workflow_compensations_triggered_total = _CounterWrapper(
    'workflow_compensations_triggered_total',
    'Total number of workflow compensations triggered',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'failed_step_name', 'tenant_id')
)

workflow_compensations_completed_total = _CounterWrapper(
    'workflow_compensations_completed_total',
    'Total number of workflow compensations completed',
    unit='1',
    expected_labels=('workflow_name', 'workflow_version', 'status', 'tenant_id')
)

workflow_compensation_duration_seconds = _HistogramWrapper(
    'workflow_compensation_duration_seconds',
    'Workflow compensation duration in seconds',
    unit='s',
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
    expected_labels=('workflow_name', 'workflow_version', 'status', 'tenant_id')
)


# ============================================================================
# Workflow Performance Metrics
# ============================================================================

# Steps per workflow histogram
workflow_steps_per_instance = _HistogramWrapper(
    'workflow_steps_per_instance',
    'Number of steps per workflow instance',
    unit='1',
    buckets=(1.0, 5.0, 10.0, 20.0, 50.0, 100.0),
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)

# Workflow state size metrics
workflow_state_size_bytes = _HistogramWrapper(
    'workflow_state_size_bytes',
    'Workflow state data size in bytes',
    unit='By',
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),
    expected_labels=('workflow_name', 'workflow_version', 'tenant_id')
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_tenant_id(tenant_id: Optional[str]) -> str:
    """
    Get tenant ID for metrics labels (use 'system' if None).
    
    Args:
        tenant_id: Tenant ID or None
        
    Returns:
        Tenant ID string or 'system'
    """
    return str(tenant_id) if tenant_id else 'system'


def get_error_type(error_details: Optional[Dict[str, Any]]) -> str:
    """
    Extract error type from error details for metrics labels.
    
    Args:
        error_details: Error details dictionary
        
    Returns:
        Error type string or 'unknown'
    """
    if not error_details:
        return 'unknown'
    
    error_type = error_details.get('exception_type', 'unknown')
    # Normalize common error types
    if 'ValidationError' in error_type:
        return 'validation_error'
    elif 'IntegrityError' in error_type:
        return 'integrity_error'
    elif 'Timeout' in error_type or 'timeout' in error_type.lower():
        return 'timeout'
    elif 'Connection' in error_type:
        return 'connection_error'
    else:
        return error_type.lower().replace('error', '').replace('exception', '').strip() or 'unknown'

