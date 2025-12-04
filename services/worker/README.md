# Worker Service

Worker service for processing jobs from Redis-backed queues with priority support, concurrency limits, and starvation prevention.

## Overview

The worker service processes jobs from three priority queues:
- **job_critical** (HIGH priority): DQ runs, compliance runs
- **job_default** (NORMAL priority): Semantic mapping, contract migration
- **job_low** (LOW priority): Contract validation

## Architecture

- **Job Queue Library**: django-rq (Decision documented in `openspec/changes/implement-second-backend-wave/design.md`)
- **Queue Implementation**: Separate physical Redis queues per priority level
- **Worker Selection**: Polls queues in priority order (job_critical → job_default → job_low)
- **Concurrency**: Reserved slots for HIGH priority jobs (50% of max concurrency by default)
- **Starvation Prevention**: Elevates NORMAL priority jobs after 5-minute wait threshold

## Running the Worker

### Using Django Management Command

```bash
# Process all priority queues
python manage.py rqworker job_critical job_default job_low

# Process only HIGH priority queue
python manage.py rqworker job_critical

# Process only NORMAL and LOW priority queues
python manage.py rqworker job_default job_low
```

### Using Standalone Entry Point

```bash
# Process all priority queues
python services/worker/main.py job_critical job_default job_low

# Process specific queues
python services/worker/main.py job_critical
```

### Using Docker Compose

The worker service is configured in `docker-compose.yml` to process all priority queues:

```bash
docker compose up worker-service
```

## Configuration

### Queue Configuration

Queues are configured in `hub/settings.py`:

```python
RQ_QUEUES = {
    'job_critical': {  # HIGH priority
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 1800,  # 30 minutes
    },
    'job_default': {  # NORMAL priority
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 360,  # 6 minutes
    },
    'job_low': {  # LOW priority
        'URL': REDIS_URL,
        'DEFAULT_TIMEOUT': 60,  # 1 minute
    },
}
```

### Worker Concurrency

Configure worker concurrency limits in `hub/settings.py`:

```python
WORKER_MAX_CONCURRENCY = 4  # Maximum concurrent jobs per worker
WORKER_MAX_CONCURRENCY_PER_TENANT = 2  # Maximum concurrent jobs per tenant
```

### Reserved Slots

Reserved slots for HIGH priority jobs are configured as a percentage of max concurrency (default: 50%).

## Job Processing

The worker processes jobs by:
1. Polling queues in priority order
2. Checking tenant concurrency limits before processing
3. Updating job status (RUNNING → SUCCEEDED/FAILED)
4. Releasing concurrency slots on completion
5. Handling timeouts and retries

## Health Checks

The worker service includes an HTTP server (port 8080, configurable via `WORKER_HEALTH_PORT`) with health check endpoints:

- `GET /healthz` - Liveness probe (returns 200 if process is running)
- `GET /ready` - Readiness probe (returns 200 if dependencies ready, 503 if not)
- `GET /metrics` - Prometheus metrics endpoint

The health check server runs in a background thread alongside the job processing worker.

### Health Check Configuration

Health check port can be configured via environment variable:
```bash
WORKER_HEALTH_PORT=8080  # Default port for health checks
```

In Docker Compose, the health check is configured:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8080/healthz"]
  interval: 30s
  timeout: 10s
  retries: 3
```

## Monitoring

### Prometheus Metrics

The worker service exposes Prometheus metrics at `/metrics` endpoint:

**Job Processing Metrics:**
- `jobs_started_total` - Counter of jobs started (labels: job_type, tenant_id)
- `jobs_completed_total` - Counter of jobs completed (labels: job_type, status, tenant_id)
- `jobs_failed_total` - Counter of jobs failed (labels: job_type, error_code, tenant_id)
- `job_duration_seconds` - Histogram of job processing duration (labels: job_type, status)
- `job_queue_length` - Gauge of current queue depth (labels: job_type, queue_name)

**Per-Tenant Metrics:**
- `tenant_running_jobs` - Gauge of running jobs per tenant (label: tenant_id)
- `tenant_queued_jobs` - Gauge of queued jobs per tenant (label: tenant_id)

### Structured Logging

The worker service uses structured logging (structlog) with the following fields:
- `job_id` - UUID of the job
- `tenant_id` - UUID of the tenant
- `job_type` - Type of job (DQ_RUN, COMPLIANCE_RUN, etc.)
- `status` - Job status (RUNNING, COMPLETED, FAILED)
- `duration_seconds` - Job processing duration (for completed/failed jobs)
- `error_type`, `error_code`, `error_message` - Error details (for failed jobs)
- `queue_name`, `slot_type`, `is_elevated` - Queue and slot information

## Scaling Strategies

### Horizontal Scaling

The worker service can be scaled horizontally by running multiple worker instances:

```bash
# Scale worker service to 3 instances
docker compose up --scale worker-service=3
```

Each worker instance:
- Processes jobs from all priority queues independently
- Respects global concurrency limits (reserved slots, shared slots)
- Shares Redis queues (job_critical, job_default, job_low)
- Updates Prometheus metrics independently

**Best Practices:**
- Monitor queue depth to determine when to scale
- Scale based on `job_queue_length` metric
- Ensure Redis has sufficient capacity for multiple workers
- Use load balancer for health check endpoints if needed

### Queue-Specific Workers

For fine-grained control, you can run workers dedicated to specific queues:

```bash
# High-priority worker (only processes job_critical)
docker compose run worker-service python services/worker/main.py job_critical

# Normal-priority worker (only processes job_default)
docker compose run worker-service python services/worker/main.py job_default

# Low-priority worker (only processes job_low)
docker compose run worker-service python services/worker/main.py job_low
```

**Use Cases:**
- Dedicated workers for critical jobs (DQ/compliance runs)
- Separate workers for quick validation jobs
- Resource isolation between job types

### Configuration Tuning

Adjust worker concurrency based on workload:

```bash
# High-throughput configuration
WORKER_MAX_CONCURRENCY=8
WORKER_RESERVED_SLOTS_RATIO=0.5  # 4 reserved, 4 shared

# Low-latency configuration (more reserved slots)
WORKER_MAX_CONCURRENCY=6
WORKER_RESERVED_SLOTS_RATIO=0.67  # 4 reserved, 2 shared
```

### Monitoring Scaling Decisions

Key metrics to monitor:
- `job_queue_length` - Queue depth per job type
- `tenant_queued_jobs` - Per-tenant queue depth
- `jobs_started_total` - Job processing rate
- `job_duration_seconds` - Average job duration

Scale up when:
- Queue depth consistently > 50 jobs
- Average wait time > 5 minutes
- Job processing rate < job creation rate

Scale down when:
- Queue depth consistently < 10 jobs
- Worker utilization < 30%
- No jobs waiting for > 10 minutes

## See Also

- **Design Decision**: `openspec/changes/implement-second-backend-wave/design.md` (Decision 2, Decision 3)
- **Specification**: `openspec/changes/implement-second-backend-wave/specs/worker-service/spec.md`
- **Implementation Tasks**: `openspec/changes/implement-second-backend-wave/tasks.md` (Phase 2)

