# RB-QUEUE-001: Queue Backlog / Throttling

**Runbook ID:** `RB-QUEUE-001`  
**Title:** Queue Backlog / Throttling  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers response procedures for high queue backlog, job lag, and queue throttling issues.

**In Scope:**
- High queue depth
- Jobs stuck in PENDING
- Worker failures
- Queue throttling

**Out of Scope:**
- Individual job failures (handled in job processing)
- Database issues affecting jobs (see `RB-DB-001`)

---

## Symptoms

### Alert Names

- `queue_depth_high` - Queue depth exceeds threshold
- `job_lag_high` - Jobs waiting too long
- `queue_throttling_detected` - Queue throttling active

### User-Visible Symptoms

- Jobs stuck in `PENDING` status
- Long job wait times
- Job timeouts
- "Job queue full" errors

### Log Examples

```
WARN: Queue depth high: 500 jobs pending
ERROR: Job timeout: job-id-123 exceeded timeout
WARN: Worker process crashed: worker-456
```

---

## Detection & Diagnosis

### Step 1: Check Queue Depth

```bash
# Check Redis queue depth
redis-cli LLEN rq:queue:default

# Check job counts by status
python manage.py shell
>>> from hub.apps.jobs.models import Job, JobStatus
>>> Job.objects.filter(status=JobStatus.PENDING).count()
```

### Step 2: Check Worker Health

```bash
# Check worker processes
kubectl get pods -l app=worker-service -n production

# Check worker logs
kubectl logs -f deployment/worker-service -n production

# Check worker metrics
# Grafana dashboard: Worker Health
```

### Step 3: Determine Backlog Cause

**Organic Load Spike:**
- Sudden increase in job submissions
- Normal worker capacity exceeded
- Temporary backlog

**Worker Failure:**
- Workers crashed or not running
- Worker errors preventing processing
- Resource exhaustion

**Downstream Dependency:**
- External service unavailable
- Database connection issues
- Object storage issues

---

## Immediate Actions

### Step 1: Pause Non-Critical Job Producers

```bash
# Disable non-critical job types
kubectl set env deployment/api-service \
  DISABLE_BATCH_JOBS=true \
  -n production

# Or via feature flag
# Set feature flag: batch_jobs_enabled = false
```

### Step 2: Restart Workers (if crashed)

```bash
# Restart worker deployment
kubectl rollout restart deployment/worker-service -n production

# Scale workers up
kubectl scale deployment/worker-service --replicas=5 -n production
```

### Step 3: Stop Affected Job Types

```bash
# If downstream dependency broken
# Stop sending affected job types
python manage.py pause_job_type --job-type DQ_RUN
```

---

## Remediation

### Step 1: Scale Workers

**Horizontal Scaling:**
```bash
# Increase worker replicas
kubectl scale deployment/worker-service --replicas=10 -n production

# Monitor queue depth
watch -n 5 'redis-cli LLEN rq:queue:default'
```

**Vertical Scaling:**
```bash
# Increase worker resources
kubectl set resources deployment/worker-service \
  --requests=cpu=2,memory=4Gi \
  --limits=cpu=4,memory=8Gi \
  -n production
```

### Step 2: Tune Rate Limits

**Per-Tenant Limits:**
```python
# Update settings
JOB_RATE_LIMIT_PER_TENANT = 50  # jobs per minute
```

**Per-Job-Type Limits:**
```python
# Limit specific job types
JOB_RATE_LIMITS = {
    'DQ_RUN': 10,  # per minute
    'COMPLIANCE_RUN': 10,
}
```

### Step 3: Drain Queue

**Prioritize Critical Jobs:**
```bash
# Process high-priority jobs first
# Update job priority in queue
python manage.py prioritize_jobs --job-type CONTRACT_VALIDATION
```

**Drain in Batches:**
```bash
# Process jobs in controlled batches
# Monitor queue depth
# Gradually increase worker capacity
```

---

## Validation

### Success Criteria

**Queue is healthy when:**
- ✅ Queue depth < 100 jobs
- ✅ Job lag < 5 minutes
- ✅ Worker utilization < 80%
- ✅ Job failure rate < 1%

### Validation Steps

**1. Check Queue Metrics:**
```bash
# Queue depth
redis-cli LLEN rq:queue:default

# Job lag
python manage.py check_job_lag
```

**2. Monitor Worker Health:**
```bash
# Worker status
kubectl get pods -l app=worker-service -n production

# Worker logs
kubectl logs deployment/worker-service -n production --tail=100
```

**3. Verify Job Processing:**
```bash
# Check job completion rate
python manage.py check_job_stats
```

---

## Communication

**Internal:**
```
⚠️ Queue Backlog Detected
Status: Remediating
Action: Scaling workers
ETA: 15 minutes
```

**Resolution:**
```
✅ Queue Backlog Resolved
Status: Healthy
Queue Depth: 50 jobs
Job Lag: 2 minutes
```

---

## Post-Incident

- [ ] Document incident
- [ ] Review worker capacity
- [ ] Update rate limits
- [ ] Improve monitoring

---

## Related Runbooks

- `RB-DB-001`: Database Outage
- `RB-SVC-001`: Service Crash Recovery

