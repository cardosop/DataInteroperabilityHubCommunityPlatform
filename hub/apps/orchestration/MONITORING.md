# Workflow Orchestration Monitoring and Observability

Complete guide for monitoring and observability of workflow orchestration system.

## Overview

The workflow orchestration system provides comprehensive monitoring and observability through:

- **Prometheus Metrics**: Detailed metrics for workflow instances, steps, execution times, failures, and retries
- **OpenTelemetry Tracing**: Distributed tracing for workflow execution and step-level visibility
- **Grafana Dashboards**: Pre-built dashboards for workflow health monitoring
- **Alerting**: Automated alerting for failures, timeouts, retry exhaustion, and stuck workflows

---

## Prometheus Metrics

### Workflow Instance Metrics

#### Counters

- **`workflow_instances_created_total`**: Total number of workflow instances created
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  
- **`workflow_instances_started_total`**: Total number of workflow instances started
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  
- **`workflow_instances_completed_total`**: Total number of workflow instances completed
  - Labels: `workflow_name`, `workflow_version`, `status`, `tenant_id`
  
- **`workflow_instances_failed_total`**: Total number of workflow instances failed
  - Labels: `workflow_name`, `workflow_version`, `error_type`, `tenant_id`
  
- **`workflow_instances_cancelled_total`**: Total number of workflow instances cancelled
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  
- **`workflow_instances_retried_total`**: Total number of workflow instance retries
  - Labels: `workflow_name`, `workflow_version`, `retry_count`, `tenant_id`
  
- **`workflow_instances_timed_out_total`**: Total number of workflow instances that timed out
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`

#### Histograms

- **`workflow_execution_duration_seconds`**: Workflow execution duration in seconds
  - Labels: `workflow_name`, `workflow_version`, `status`, `tenant_id`
  - Buckets: `1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0, 3600.0, 7200.0`

#### Gauges

- **`workflow_instances_running`**: Current number of running workflow instances
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  
- **`workflow_instances_pending`**: Current number of pending workflow instances
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  
- **`workflow_instances_failed_current`**: Current number of failed workflow instances (not yet retried or cleaned up)
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`

### Workflow Step Metrics

#### Counters

- **`workflow_steps_started_total`**: Total number of workflow steps started
  - Labels: `workflow_name`, `workflow_version`, `step_name`, `step_type`, `tenant_id`
  
- **`workflow_steps_completed_total`**: Total number of workflow steps completed
  - Labels: `workflow_name`, `workflow_version`, `step_name`, `step_type`, `status`, `tenant_id`
  
- **`workflow_steps_failed_total`**: Total number of workflow steps failed
  - Labels: `workflow_name`, `workflow_version`, `step_name`, `step_type`, `error_type`, `tenant_id`
  
- **`workflow_steps_retried_total`**: Total number of workflow step retries
  - Labels: `workflow_name`, `workflow_version`, `step_name`, `step_type`, `retry_count`, `tenant_id`

#### Histograms

- **`workflow_step_execution_duration_seconds`**: Workflow step execution duration in seconds
  - Labels: `workflow_name`, `workflow_version`, `step_name`, `step_type`, `status`, `tenant_id`
  - Buckets: `0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0`

### Workflow Compensation Metrics

#### Counters

- **`workflow_compensations_triggered_total`**: Total number of workflow compensations triggered
  - Labels: `workflow_name`, `workflow_version`, `failed_step_name`, `tenant_id`
  
- **`workflow_compensations_completed_total`**: Total number of workflow compensations completed
  - Labels: `workflow_name`, `workflow_version`, `status`, `tenant_id`

#### Histograms

- **`workflow_compensation_duration_seconds`**: Workflow compensation duration in seconds
  - Labels: `workflow_name`, `workflow_version`, `status`, `tenant_id`
  - Buckets: `1.0, 5.0, 10.0, 30.0, 60.0, 300.0`

### Workflow Performance Metrics

#### Histograms

- **`workflow_steps_per_instance`**: Number of steps per workflow instance
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  - Buckets: `1.0, 5.0, 10.0, 20.0, 50.0, 100.0`
  
- **`workflow_state_size_bytes`**: Workflow state data size in bytes
  - Labels: `workflow_name`, `workflow_version`, `tenant_id`
  - Buckets: `1024, 10240, 102400, 1048576, 10485760, 104857600`

### Example Prometheus Queries

```promql
# Workflow success rate
(sum(rate(workflow_instances_completed_total{status="COMPLETED"}[5m])) by (workflow_name) 
 / sum(rate(workflow_instances_started_total[5m])) by (workflow_name)) * 100

# Workflow execution duration P95
histogram_quantile(0.95, sum(rate(workflow_execution_duration_seconds_bucket[5m])) by (workflow_name, le))

# Current running workflows
sum(workflow_instances_running) by (workflow_name)

# Workflow failure rate
sum(rate(workflow_instances_failed_total[5m])) by (workflow_name, error_type)
```

---

## OpenTelemetry Tracing

### Trace Structure

Workflow execution creates distributed traces with the following structure:

```
workflow.execute.{workflow_name}
├── workflow.step.{step_name}
│   └── (step execution details)
├── workflow.step.{step_name}
│   └── (step execution details)
└── workflow.compensation.{workflow_name} (if compensation triggered)
    └── (compensation details)
```

### Trace Attributes

#### Workflow Instance Span

- `workflow.instance_id`: Workflow instance UUID
- `workflow.name`: Workflow name
- `workflow.version`: Workflow version
- `workflow.tenant_id`: Tenant ID (or "system")
- `workflow.status`: Final workflow status (COMPLETED, FAILED)
- `workflow.duration_seconds`: Total execution duration
- `workflow.steps_completed`: Number of steps completed
- `workflow.error_type`: Error type (if failed)

#### Workflow Step Span

- `workflow.instance_id`: Workflow instance UUID
- `workflow.name`: Workflow name
- `workflow.step.name`: Step name
- `workflow.step.type`: Step type (task, parallel, conditional, etc.)
- `workflow.step.index`: Step index (0-based)
- `workflow.step.status`: Step status (COMPLETED, FAILED)
- `workflow.step.duration_seconds`: Step execution duration
- `workflow.step.error_type`: Error type (if failed)

#### Compensation Span

- `workflow.instance_id`: Workflow instance UUID
- `workflow.name`: Workflow name
- `workflow.failed_step`: Name of the failed step that triggered compensation
- `workflow.compensation.status`: Compensation status (COMPLETED, FAILED)
- `workflow.compensation.duration_seconds`: Compensation duration

### Trace Sampling

- **Development**: 100% sampling (all traces)
- **Production**: 10% sampling (configurable via `OPENTELEMETRY_ENABLED` and sampling rate)

---

## Grafana Dashboards

### Workflow Orchestration Dashboard

**Location**: `monitoring/grafana/dashboards/workflow-orchestration.json`

**Panels**:

1. **Workflow Instance Throughput**: Rate of workflow completions by workflow name and status
2. **Workflow Success Rate**: Percentage of successful workflow executions
3. **Workflow Execution Duration (P95)**: 95th percentile execution duration
4. **Workflow Failure Rate**: Rate of workflow failures by error type
5. **Current Running Workflows**: Current count of running workflow instances
6. **Current Failed Workflows**: Current count of failed workflow instances
7. **Workflow Retry Rate**: Rate of workflow retries
8. **Workflow Timeouts**: Rate of workflow timeouts
9. **Step Execution Duration (P95)**: 95th percentile step execution duration
10. **Step Failure Rate**: Rate of step failures by error type
11. **Workflow Compensation Rate**: Rate of workflow compensations triggered
12. **Workflow State Size**: Distribution of workflow state sizes
13. **Steps per Workflow Instance**: Distribution of steps per workflow
14. **Workflow Instance Status Distribution**: Pie chart of workflow statuses

**Variables**:

- `workflow_name`: Filter by workflow name (supports multi-select)
- `tenant_id`: Filter by tenant ID (supports multi-select)

**Import Instructions**:

1. Access Grafana at `http://localhost:3000`
2. Navigate to "+" → "Import"
3. Upload `monitoring/grafana/dashboards/workflow-orchestration.json`
4. Configure Prometheus data source
5. Save dashboard

---

## Alerting

### Alert Types

#### 1. Workflow Timeout Alert

**Condition**: Workflow instance has been running longer than the timeout threshold

**Severity**: High

**Alert Fields**:
- `alert_type`: "workflow_timeout"
- `workflow_instance_id`: UUID of the timed-out instance
- `workflow_name`: Name of the workflow
- `workflow_version`: Version of the workflow
- `started_at`: When the workflow started
- `timeout_threshold`: The timeout threshold that was exceeded

**Configuration**:
- Default timeout threshold: 3600 seconds (1 hour)
- Configurable per workflow via `timeout_seconds` field

#### 2. Workflow Failure Rate Alert

**Condition**: High number of workflow failures in a time window

**Severity**: High

**Alert Fields**:
- `alert_type`: "workflow_failure_rate"
- `workflow_name`: Name of the workflow
- `failure_count`: Number of failures in the time window
- `time_window_minutes`: Time window checked

**Configuration**:
- Default minimum failures: 5
- Default time window: 15 minutes

#### 3. Retry Exhaustion Alert

**Condition**: Workflow instance has exhausted all retry attempts

**Severity**: Critical

**Alert Fields**:
- `alert_type`: "workflow_retry_exhaustion"
- `workflow_instance_id`: UUID of the exhausted instance
- `retry_count`: Number of retries attempted
- `max_retries`: Maximum retries allowed
- `error_message`: Error message from the last failure

#### 4. Stuck Workflow Alert

**Condition**: Workflow instance appears stuck (no progress for threshold time)

**Severity**: Medium

**Alert Fields**:
- `alert_type`: "workflow_stuck"
- `workflow_instance_id`: UUID of the stuck instance
- `stuck_step_name`: Name of the step that's stuck
- `stuck_step_index`: Index of the stuck step
- `step_started_at`: When the step started

**Configuration**:
- Default stuck threshold: 30 minutes

#### 5. Step Failure Rate Alert

**Condition**: High failure rate for a specific workflow step

**Severity**: High

**Alert Fields**:
- `alert_type`: "step_failure_rate"
- `workflow_name`: Name of the workflow
- `step_name`: Name of the failing step
- `failure_count`: Number of failures
- `total_attempts`: Total number of attempts
- `failure_rate`: Failure rate (0.0-1.0)

**Configuration**:
- Default minimum failure rate: 0.5 (50%)
- Default minimum failures: 10
- Default time window: 60 minutes

### Using the Alerting Service

```python
from hub.apps.orchestration.alerting import WorkflowAlerting

# Initialize alerting service
alerting = WorkflowAlerting()

# Check all alert conditions
alerts = alerting.check_all_alerts(
    timeout_threshold_seconds=3600,
    failure_rate_window_minutes=15,
    stuck_threshold_minutes=30
)

# Check specific alert types
timeout_alerts = alerting.check_workflow_timeouts(timeout_threshold_seconds=3600)
failure_alerts = alerting.check_failed_workflows(min_failure_count=5)
retry_alerts = alerting.check_retry_exhaustion()
stuck_alerts = alerting.check_stuck_workflows(stuck_threshold_minutes=30)
step_alerts = alerting.check_step_failure_rate(min_failure_rate=0.5)

# Send individual alert
alert = {
    "alert_type": "workflow_timeout",
    "severity": "high",
    "workflow_instance_id": "123e4567-e89b-12d3-a456-426614174000",
    "message": "Workflow timed out"
}
alerting.send_alert(alert)
```

### Alert Integration

Alerts are currently logged via Python logging. To integrate with external alerting systems:

1. **PagerDuty**: Use PagerDuty Events API
2. **Slack**: Use Slack Webhook API
3. **Email**: Use Django email backend
4. **Prometheus Alertmanager**: Export alerts as Prometheus alert rules

Example integration:

```python
def send_alert(self, alert: Dict[str, Any]) -> bool:
    """Send alert to external system"""
    # Log alert
    logger.warning(f"Workflow alert: {alert['alert_type']}", extra={"alert": alert})
    
    # Send to PagerDuty
    if alert['severity'] == 'critical':
        send_pagerduty_alert(alert)
    
    # Send to Slack
    send_slack_notification(alert)
    
    return True
```

---

## Best Practices

### Metrics Cardinality

- **Avoid high-cardinality labels**: Don't use unique IDs (like workflow_instance_id) as labels
- **Use aggregation**: Aggregate metrics by workflow_name, tenant_id, status
- **Use logs/traces for details**: Use logs and traces for per-instance analysis

### Tracing Best Practices

- **Span naming**: Use consistent naming: `workflow.execute.{workflow_name}`, `workflow.step.{step_name}`
- **Attribute naming**: Use dot notation: `workflow.instance_id`, `workflow.step.name`
- **Error recording**: Always record exceptions using `span.record_exception()`

### Alerting Best Practices

- **Alert on trends**: Alert on failure rates, not individual failures
- **Set appropriate thresholds**: Adjust thresholds based on normal operation
- **Avoid alert fatigue**: Don't alert on transient issues
- **Use severity levels**: Use severity levels to prioritize alerts

### Dashboard Best Practices

- **Use variables**: Use Grafana variables for filtering
- **Set refresh intervals**: Set appropriate refresh intervals (30s for real-time, 5m for trends)
- **Add descriptions**: Add panel descriptions and tooltips
- **Organize panels**: Group related panels together

---

## Troubleshooting

### Metrics Not Appearing

1. **Check Prometheus configuration**: Ensure Prometheus is scraping the `/metrics` endpoint
2. **Check metric initialization**: Verify OpenTelemetry metrics are initialized
3. **Check labels**: Ensure all required labels are provided

### Traces Not Appearing

1. **Check OpenTelemetry configuration**: Verify `OPENTELEMETRY_ENABLED` is set
2. **Check Jaeger**: Ensure Jaeger is running and accessible
3. **Check sampling**: Verify sampling rate is appropriate

### Alerts Not Triggering

1. **Check alert thresholds**: Verify thresholds are set correctly
2. **Check time windows**: Ensure time windows are appropriate
3. **Check alert service**: Verify alert service is running

---

## References

- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [OpenTelemetry Python](https://opentelemetry.io/docs/instrumentation/python/)
- [Grafana Dashboard Documentation](https://grafana.com/docs/grafana/latest/dashboards/)
- [Workflow Engine Documentation](./workflow_engine.py)

