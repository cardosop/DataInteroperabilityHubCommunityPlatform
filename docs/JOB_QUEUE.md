# Job Queue Documentation

## Overview

The Data Interoperability Hub uses a Redis-backed job queue system (django-rq) for processing asynchronous jobs. This document describes the job priority queue architecture, retry configuration, strategy, and monitoring.

## Job Priority Queue Architecture

### Priority Levels

The system supports three priority levels:
- **HIGH**: Critical long-running jobs (DQ runs, compliance runs)
- **NORMAL**: Standard jobs (semantic mapping, contract migration, scheduled ingestion, etc.)
- **LOW**: Quick validation jobs (contract validation)

### Priority Assignment Rules

Priority is assigned using the following rules (in order):
1. **Explicit Priority**: If priority is explicitly provided when creating a job, use it
2. **Job Type Rules**: If job_type has a priority rule in `JOB_PRIORITY_RULES`, use it
3. **Default Priority**: Otherwise, use `JOB_PRIORITY_DEFAULT` (default: NORMAL)

### Priority Queue Implementation

The priority queue system uses **separate physical Redis queues** per priority level:
- **job_critical**: HIGH priority jobs
- **job_default**: NORMAL priority jobs
- **job_low**: LOW priority jobs

This approach provides:
- **Simple implementation**: No complex priority sorting logic needed
- **Worker selection**: Workers poll queues in priority order (job_critical → job_default → job_low)
- **Concurrency control**: Reserved slots for HIGH priority jobs (50% of max concurrency by default)
- **Starvation prevention**: NORMAL priority jobs are elevated to HIGH after 5-minute wait threshold

### Priority Queue Configuration

Priority configuration is defined in `hub/settings.py`:

```python
# Default priority for jobs when not explicitly specified
JOB_PRIORITY_DEFAULT = "NORMAL"

# Priority assignment rules by job type
JOB_PRIORITY_RULES = {
    # HIGH priority: Critical long-running jobs
    "DQ_RUN": "HIGH",
    "COMPLIANCE_RUN": "HIGH",
    # NORMAL priority: Standard jobs (default)
    "SEMANTIC_MAPPING": "NORMAL",
    "CONTRACT_MIGRATION": "NORMAL",
    # ... other job types
    # LOW priority: Quick validation jobs
    "CONTRACT_VALIDATION": "LOW",
}
```

### Priority Queue Monitoring

The following Prometheus metrics track priority queue behavior:

- **`job_queue_length_by_priority`** (Gauge): Current number of jobs in queue by priority
  - Labels: `priority`, `job_type`
  - Example: `job_queue_length_by_priority{priority="HIGH", job_type="DQ_RUN"}`

- **`job_processing_rate_by_priority`** (Counter): Total number of jobs processed per second by priority
  - Labels: `priority`, `job_type`
  - Example: `job_processing_rate_by_priority{priority="HIGH", job_type="DQ_RUN"}`

### Using Priority in Job Creation

```python
from hub.apps.jobs.utils import create_job
from hub.apps.jobs.models import JobPriority

# Create job with explicit priority
job = create_job(
    job_type="DQ_RUN",
    resource_type="DATASET",
    resource_id=str(resource_id),
    priority=JobPriority.HIGH  # Explicit priority
)

# Create job with priority determined from job_type rules
job = create_job(
    job_type="DQ_RUN",  # Will use HIGH priority from JOB_PRIORITY_RULES
    resource_type="DATASET",
    resource_id=str(resource_id)
)
```

## Job Retry Strategy

### Exponential Backoff

The system uses an exponential backoff strategy for retrying failed jobs. The retry delay increases exponentially with each retry attempt:

**Formula**: `delay = base_delay * (2 ^ retry_count)`

**Example delays** (with base delay of 60 seconds):
- Retry 1: 60 seconds (1 minute)
- Retry 2: 120 seconds (2 minutes)
- Retry 3: 240 seconds (4 minutes)
- Retry 4: 480 seconds (8 minutes)

### Retry Configuration

Retry configuration is centralized in Django settings and can be customized per job type:

- **`JOB_RETRY_MAX_ATTEMPTS`**: Maximum number of retry attempts per job type (dict)
- **`JOB_RETRY_INITIAL_DELAY`**: Initial delay before first retry per job type (dict, in seconds)
- **`JOB_RETRY_MAX_DELAY`**: Maximum delay cap per job type (dict, in seconds)
- **`JOB_RETRY_BACKOFF_FACTOR`**: Exponential backoff factor per job type (dict, default: 2)

### Default Retry Configuration

Default retry settings (can be overridden in `settings.py`):

```python
JOB_RETRY_MAX_ATTEMPTS = {
    'DQ_RUN': 3,
    'COMPLIANCE_RUN': 3,
    'CONTRACT_VALIDATION': 2,
    'SEMANTIC_MAPPING': 2,
    'CONTRACT_MIGRATION': 1,
    'SCHEDULED_INGESTION': 2,
    'RETENTION_POLICY_ENFORCEMENT': 1,
    'SEARCH_INDEX_UPDATE': 2,
    'ODPS_NORMALIZATION': 2,
    'ODPS_REF_RESOLUTION': 2,
    'ODPS_EXPORT': 2,
    'ODPS_SEMANTIC_MAPPING': 2,
    'ODPS_LINKING': 2,
    'TRANSFORMATION_PIPELINE_EXECUTION': 2,
    'VIRTUAL_QUERY_EXECUTION': 2,
}

JOB_RETRY_INITIAL_DELAY = {
    'DQ_RUN': 60,  # 1 minute
    'COMPLIANCE_RUN': 60,  # 1 minute
    'CONTRACT_VALIDATION': 30,  # 30 seconds
    'SEMANTIC_MAPPING': 30,  # 30 seconds
    'CONTRACT_MIGRATION': 60,  # 1 minute
    'SCHEDULED_INGESTION': 120,  # 2 minutes
    'RETENTION_POLICY_ENFORCEMENT': 60,  # 1 minute
    'SEARCH_INDEX_UPDATE': 30,  # 30 seconds
    'ODPS_NORMALIZATION': 60,  # 1 minute
    'ODPS_REF_RESOLUTION': 60,  # 1 minute
    'ODPS_EXPORT': 30,  # 30 seconds
    'ODPS_SEMANTIC_MAPPING': 60,  # 1 minute
    'ODPS_LINKING': 30,  # 30 seconds
    'TRANSFORMATION_PIPELINE_EXECUTION': 60,  # 1 minute
    'VIRTUAL_QUERY_EXECUTION': 60,  # 1 minute
}

JOB_RETRY_MAX_DELAY = {
    'DQ_RUN': 3600,  # 1 hour
    'COMPLIANCE_RUN': 3600,  # 1 hour
    'CONTRACT_VALIDATION': 600,  # 10 minutes
    'SEMANTIC_MAPPING': 600,  # 10 minutes
    'CONTRACT_MIGRATION': 1800,  # 30 minutes
    'SCHEDULED_INGESTION': 3600,  # 1 hour
    'RETENTION_POLICY_ENFORCEMENT': 1800,  # 30 minutes
    'SEARCH_INDEX_UPDATE': 600,  # 10 minutes
    'ODPS_NORMALIZATION': 1800,  # 30 minutes
    'ODPS_REF_RESOLUTION': 1800,  # 30 minutes
    'ODPS_EXPORT': 600,  # 10 minutes
    'ODPS_SEMANTIC_MAPPING': 1800,  # 30 minutes
    'ODPS_LINKING': 600,  # 10 minutes
    'TRANSFORMATION_PIPELINE_EXECUTION': 1800,  # 30 minutes
    'VIRTUAL_QUERY_EXECUTION': 1800,  # 30 minutes
}

JOB_RETRY_BACKOFF_FACTOR = {
    'DQ_RUN': 2,
    'COMPLIANCE_RUN': 2,
    'CONTRACT_VALIDATION': 2,
    'SEMANTIC_MAPPING': 2,
    'CONTRACT_MIGRATION': 2,
    'SCHEDULED_INGESTION': 2,
    'RETENTION_POLICY_ENFORCEMENT': 2,
    'SEARCH_INDEX_UPDATE': 2,
    'ODPS_NORMALIZATION': 2,
    'ODPS_REF_RESOLUTION': 2,
    'ODPS_EXPORT': 2,
    'ODPS_SEMANTIC_MAPPING': 2,
    'ODPS_LINKING': 2,
    'TRANSFORMATION_PIPELINE_EXECUTION': 2,
    'VIRTUAL_QUERY_EXECUTION': 2,
}
```

### Retry Delay Calculation

The retry delay is calculated using exponential backoff with configurable factors:

```python
delay = initial_delay * (backoff_factor ^ retry_count)
delay = min(delay, max_delay)  # Cap at max_delay
```

**Example** (DQ_RUN with default config):
- Retry 1: `60 * (2 ^ 0) = 60` seconds (capped at 3600)
- Retry 2: `60 * (2 ^ 1) = 120` seconds (capped at 3600)
- Retry 3: `60 * (2 ^ 2) = 240` seconds (capped at 3600)

### Retry Timeout Configuration

Each job type has a maximum timeout that applies to both initial execution and retries:

- **`JOB_TIMEOUTS`**: Maximum execution time per job type (dict, in seconds)

See `hub/apps/jobs/utils.py` for default timeout values.

### Retry Failure Handling

#### Transient vs Non-Transient Failures

The system distinguishes between transient and non-transient failures:

**Transient failures** (will retry):
- `ConnectionError`: Service unavailable, network issues
- `TimeoutError`: Request timeout, service slow to respond
- Errors containing keywords: 'temporary', 'retry', 'service unavailable', '503', '502', '504'

**Non-transient failures** (will not retry):
- `ValueError`: Validation errors, invalid input
- `PermissionError`: Authorization failures
- `FileNotFoundError`: Missing files/resources
- Errors containing keywords: 'permission', 'not found', 'invalid', 'validation'

#### Retry Exhaustion

When retry attempts are exhausted:
1. Job status is set to `FAILED`
2. Error message is stored in `job.error_message`
3. Retry count and last retry timestamp are stored in `job.details_json`
4. Job is moved to dead letter queue (if configured)
5. Audit event is created for retry exhaustion

#### Retry State Tracking

Retry information is stored in `job.details_json`:
- `retry_count`: Current retry attempt number (0-indexed)
- `last_retry_error`: Error message from last retry attempt
- `last_retry_at`: ISO timestamp of last retry attempt

## Monitoring

### Retry Metrics

The following Prometheus metrics track job retry behavior:

- **`job_retry_count`** (Histogram): Number of retries for job processing
  - Labels: `job_type`, `queue_name`
  - Buckets: 0, 1, 2, 3, 5, 10

- **`job_retry_delay_seconds`** (Histogram): Retry delay duration in seconds
  - Labels: `job_type`
  - Buckets: 30, 60, 120, 300, 600, 1800, 3600

- **`job_retry_failures_total`** (Counter): Total number of jobs that failed after retries
  - Labels: `job_type`, `error_type`

### Retry Monitoring Dashboards

Job retry metrics are available in Grafana dashboards:
- **ODPS Job Queue Dashboard**: Shows retry count distribution for ODPS jobs
- **Job Processing Dashboard**: Shows retry metrics for all job types

## Configuration

### Environment Variables

Retry configuration can be overridden via environment variables (see `hub/settings.py`):

```bash
# Example: Override max retries for DQ_RUN
JOB_RETRY_MAX_ATTEMPTS_DQ_RUN=5

# Example: Override initial delay for ODPS_NORMALIZATION
JOB_RETRY_INITIAL_DELAY_ODPS_NORMALIZATION=120
```

### Django Settings

Retry configuration is defined in `hub/settings.py`:

```python
# Job Retry Configuration
JOB_RETRY_MAX_ATTEMPTS = {
    'DQ_RUN': 3,
    'COMPLIANCE_RUN': 3,
    # ... other job types
}

JOB_RETRY_INITIAL_DELAY = {
    'DQ_RUN': 60,
    'COMPLIANCE_RUN': 60,
    # ... other job types
}

JOB_RETRY_MAX_DELAY = {
    'DQ_RUN': 3600,
    'COMPLIANCE_RUN': 3600,
    # ... other job types
}

JOB_RETRY_BACKOFF_FACTOR = {
    'DQ_RUN': 2,
    'COMPLIANCE_RUN': 2,
    # ... other job types
}
```

## Usage

### Checking Retry Configuration

```python
from hub.apps.jobs.utils import get_job_max_retries, calculate_retry_delay

# Get max retries for a job type
max_retries = get_job_max_retries('DQ_RUN')  # Returns 3

# Calculate retry delay
delay = calculate_retry_delay(retry_count=1, base_delay=60)  # Returns 120
```

### Retrying a Job

The `retry_job()` function handles retry logic automatically:

```python
from hub.apps.jobs.utils import retry_job

# Retry a failed job
retried = retry_job(job_obj, job_type='DQ_RUN', exception=exception)
if retried:
    # Job was scheduled for retry
    pass
else:
    # No retries remaining or error is not transient
    pass
```

## Best Practices

1. **Configure appropriate retry limits**: Set max retries based on job criticality and expected failure rates
2. **Use exponential backoff**: Prevents overwhelming services during outages
3. **Monitor retry metrics**: Track retry rates and delays to identify issues
4. **Distinguish transient vs non-transient failures**: Only retry transient failures
5. **Set reasonable timeouts**: Ensure timeouts allow for retries without excessive delays
6. **Document custom retry logic**: If overriding defaults, document the rationale

## Troubleshooting

### High Retry Rates

If retry rates are high:
1. Check service health and availability
2. Review error types in `job_retry_failures_total` metric
3. Verify timeout configurations are appropriate
4. Consider increasing retry delays for overloaded services

### Retry Exhaustion

If many jobs exhaust retries:
1. Review `job_retry_failures_total` metric for error patterns
2. Check if failures are transient or non-transient
3. Consider increasing max retries for critical job types
4. Investigate root cause of persistent failures

### Retry Delays Too Long

If retry delays are causing issues:
1. Review `job_retry_delay_seconds` histogram
2. Consider reducing `JOB_RETRY_INITIAL_DELAY` for faster retries
3. Adjust `JOB_RETRY_BACKOFF_FACTOR` to reduce exponential growth
4. Set lower `JOB_RETRY_MAX_DELAY` to cap delays

## Related Documentation

- [Worker Service README](../services/worker/README.md)
- [Job Queue Monitoring Dashboards](../monitoring/grafana/dashboards/odps-job-queue.json)
- [Job Models](../hub/apps/jobs/models.py)
- [Job Utilities](../hub/apps/jobs/utils.py)

