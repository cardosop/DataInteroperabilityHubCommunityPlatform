# RB-SCHEDULED-INGESTION-001: Scheduled Ingestion Operations (Prefect Worker)

**Runbook ID:** `RB-SCHEDULED-INGESTION-001`
**Title:** Scheduled Ingestion Operations (Prefect Worker)
**Last Updated:** 2026-02-02
**Version:** 1.0

---

## Scope

This runbook covers operational procedures for scheduled ingestion using Prefect workers (Option C). It includes verification, troubleshooting, remediation, and rollback procedures.

**In Scope:**
- Verifying Prefect worker and pool status
- Correlating Prefect flow_run_id with hub run_id
- Restarting workers and redeploying flows
- Handling stuck runs and failed runs
- Rollback procedures (re-enable django-rq path if kept behind flag)

**Out of Scope:**
- Initial setup and configuration (see `docs/DOCKER_COMPOSE_DEPLOYMENT.md` and `k8s/README.md`)
- Prefect server issues (see `docs/RUNBOOKS.md` - Prefect Server Issues)
- General scheduled ingestion failures (see `docs/RUNBOOKS.md` - Scheduled Ingestion Failures)

---

## Audience & Roles

**Primary Users:**
- DevOps engineers
- SRE team members
- Platform operators

**Required Permissions:**
- Access to Prefect UI/API
- Kubernetes/Docker Compose access (for worker management)
- Hub API access (for run status queries)
- Database access (for run correlation)

---

## Prerequisites

**Tools Required:**
- `kubectl` (for Kubernetes deployments)
- `docker` / `docker-compose` (for local/staging)
- `psql` (for database queries)
- Access to Prefect UI (default: `http://localhost:4200`)
- Access to Hub API (default: `http://localhost:8000`)

**Access Required:**
- Prefect API access (`PREFECT_API_URL`, `PREFECT_API_KEY`)
- Hub API access (`HUB_BASE_URL`, `HUB_WORKER_API_KEY`)
- Database access (for run correlation queries)

**Environment Variables:**
- `PREFECT_API_URL`: Prefect API URL (e.g., `http://prefect-server:4200/api`)
- `PREFECT_API_KEY`: Prefect API key (optional, for authenticated access)
- `HUB_BASE_URL`: Hub API base URL (e.g., `http://api-service:8000`)
- `HUB_WORKER_API_KEY`: Hub worker API key (for worker authentication)

---

## 1. Verify Prefect Worker and Pool

### 1.1 Check Worker Status

**Docker Compose:**
```bash
# Check worker container status
docker-compose ps prefect-worker

# Check worker logs
docker-compose logs prefect-worker --tail=100

# Verify worker is connected to Prefect server
docker-compose exec prefect-worker prefect worker status
```

**Kubernetes:**
```bash
# Check worker pod status
kubectl get pods -l app=prefect-worker -n prefect

# Check worker logs
kubectl logs -l app=prefect-worker -n prefect --tail=100

# Describe pod for events/status
kubectl describe pod -l app=prefect-worker -n prefect
```

**Expected Output:**
- Worker container/pod is running
- Worker logs show connection to Prefect server
- Worker status shows "Connected" or "Ready"

### 1.2 Verify Work Pool

**Via Prefect UI:**
1. Navigate to Prefect UI: `http://localhost:4200` (or configured URL)
2. Go to **Work Pools** section
3. Verify work pool exists (default: `default`)
4. Check pool status: should show active workers

**Via Prefect CLI:**
```bash
# List work pools
docker-compose exec prefect-worker prefect work-pool ls

# Inspect work pool
docker-compose exec prefect-worker prefect work-pool inspect default

# Check pool status
docker-compose exec prefect-worker prefect work-pool status default
```

**Via Prefect API:**
```bash
# Get work pools (requires PREFECT_API_KEY)
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/work_pools/"

# Get work pool details
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/work_pools/default"
```

**Expected Output:**
- Work pool exists and is active
- Pool shows at least one active worker
- Pool configuration matches deployment (e.g., `process` type)

### 1.3 Verify Hub API Connectivity

**From Worker Container:**
```bash
# Test hub API health
docker-compose exec prefect-worker curl -f http://api-service:8000/health

# Test worker API endpoint (requires HUB_WORKER_API_KEY)
docker-compose exec prefect-worker bash -c \
  'curl -H "Authorization: ApiKey $HUB_WORKER_API_KEY" \
   -H "X-Tenant-ID: <tenant-id>" \
   http://api-service:8000/api/v1/scheduled-ingestions/internal/config/<scheduled-ingestion-id>/'
```

**Expected Output:**
- Health endpoint returns `200 OK`
- Config endpoint returns config (without raw credentials)
- No connection errors or timeouts

---

## 2. Correlate Prefect flow_run_id with Hub run_id

### 2.1 Find Hub Run by Prefect flow_run_id

**Via Hub API:**
```bash
# Query runs by prefect_flow_run_id (requires API access)
curl -H "Authorization: Bearer <token>" \
  "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/runs/?prefect_flow_run_id=<flow-run-id>"
```

**Via Database Query:**
```sql
-- Find hub run by Prefect flow_run_id
SELECT
    id AS hub_run_id,
    scheduled_ingestion_id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    files_found,
    files_processed,
    files_failed
FROM scheduled_ingestion_scheduledingestionrun
WHERE prefect_flow_run_id = '<prefect-flow-run-id>';
```

**Via Django Shell:**
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

# Find run by Prefect flow_run_id
run = ScheduledIngestionRun.objects.filter(
    prefect_flow_run_id='<prefect-flow-run-id>'
).first()

if run:
    print(f"Hub Run ID: {run.id}")
    print(f"Scheduled Ingestion ID: {run.scheduled_ingestion_id}")
    print(f"Status: {run.status}")
    print(f"Started At: {run.started_at}")
    print(f"Completed At: {run.completed_at}")
else:
    print("No hub run found for this Prefect flow_run_id")
```

### 2.2 Find Prefect Flow Run by Hub run_id

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Flow Runs** section
3. Search by flow name: `scheduled_ingestion_full_flow`
4. Filter by tags or parameters to find matching run

**Via Prefect API:**
```bash
# Get flow runs (requires PREFECT_API_KEY)
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/flow_runs/?flow_name=scheduled_ingestion_full_flow"

# Get specific flow run by ID
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/flow_runs/<flow-run-id>"
```

**Via Database Query (if Prefect DB accessible):**
```sql
-- Find Prefect flow run by hub run_id (if stored in flow run state/parameters)
-- Note: This requires access to Prefect database
SELECT
    id AS prefect_flow_run_id,
    name,
    state_type,
    state_name,
    start_time,
    end_time,
    parameters
FROM flow_run
WHERE parameters->>'scheduled_ingestion_id' = '<scheduled-ingestion-id>'
  AND start_time >= '<start-time-filter>';
```

### 2.3 Correlation Verification Script

**Python Script:**
```python
#!/usr/bin/env python3
"""
Correlate Prefect flow_run_id with Hub run_id.
Usage: python correlate_runs.py <prefect-flow-run-id> [--hub-run-id <hub-run-id>]
"""
import os
import sys
import requests
from uuid import UUID

PREFECT_API_URL = os.getenv("PREFECT_API_URL", "http://localhost:4200/api")
PREFECT_API_KEY = os.getenv("PREFECT_API_KEY", "")
HUB_BASE_URL = os.getenv("HUB_BASE_URL", "http://localhost:8000")
HUB_API_KEY = os.getenv("HUB_API_KEY", "")

def get_prefect_flow_run(flow_run_id: str):
    """Get Prefect flow run details."""
    headers = {}
    if PREFECT_API_KEY:
        headers["Authorization"] = f"Bearer {PREFECT_API_KEY}"

    url = f"{PREFECT_API_URL}/flow_runs/{flow_run_id}"
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()

def get_hub_run_by_prefect_id(prefect_flow_run_id: str, scheduled_ingestion_id: str):
    """Get Hub run by Prefect flow_run_id."""
    headers = {}
    if HUB_API_KEY:
        headers["Authorization"] = f"Bearer {HUB_API_KEY}"

    url = f"{HUB_BASE_URL}/api/v1/scheduled-ingestions/{scheduled_ingestion_id}/runs/"
    params = {"prefect_flow_run_id": prefect_flow_run_id}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

def correlate_runs(prefect_flow_run_id: str):
    """Correlate Prefect flow run with Hub run."""
    print(f"Fetching Prefect flow run: {prefect_flow_run_id}")
    prefect_run = get_prefect_flow_run(prefect_flow_run_id)

    scheduled_ingestion_id = prefect_run.get("parameters", {}).get("scheduled_ingestion_id")
    if not scheduled_ingestion_id:
        print("ERROR: Prefect flow run does not have scheduled_ingestion_id in parameters")
        return

    print(f"Scheduled Ingestion ID: {scheduled_ingestion_id}")
    print(f"Prefect Flow Run Status: {prefect_run.get('state_type')}")
    print(f"Prefect Flow Run Name: {prefect_run.get('name')}")

    print(f"\nFetching Hub run for Prefect flow_run_id: {prefect_flow_run_id}")
    hub_runs = get_hub_run_by_prefect_id(prefect_flow_run_id, scheduled_ingestion_id)

    if hub_runs.get("results"):
        hub_run = hub_runs["results"][0]
        print(f"\n✅ Correlation Found:")
        print(f"  Hub Run ID: {hub_run['id']}")
        print(f"  Hub Run Status: {hub_run['status']}")
        print(f"  Prefect Flow Run ID: {hub_run.get('prefect_flow_run_id')}")
        print(f"  Started At: {hub_run.get('started_at')}")
        print(f"  Completed At: {hub_run.get('completed_at')}")
        print(f"  Files Found: {hub_run.get('files_found', 0)}")
        print(f"  Files Processed: {hub_run.get('files_processed', 0)}")
        print(f"  Files Failed: {hub_run.get('files_failed', 0)}")
    else:
        print(f"\n⚠️  No Hub run found for Prefect flow_run_id: {prefect_flow_run_id}")
        print("  This may indicate:")
        print("  - Hub run was not created (check Prefect flow logs)")
        print("  - prefect_flow_run_id was not set in hub run")
        print("  - Hub API call failed during flow execution")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python correlate_runs.py <prefect-flow-run-id>")
        sys.exit(1)

    prefect_flow_run_id = sys.argv[1]
    correlate_runs(prefect_flow_run_id)
```

---

## 3. Restart Worker and Redeploy Flow

### 3.1 Restart Prefect Worker

**Docker Compose:**
```bash
# Restart worker
docker-compose restart prefect-worker

# Verify worker restarted successfully
docker-compose ps prefect-worker

# Check worker logs after restart
docker-compose logs prefect-worker --tail=50 --follow
```

**Kubernetes:**
```bash
# Restart worker deployment
kubectl rollout restart deployment/prefect-worker -n prefect

# Monitor rollout status
kubectl rollout status deployment/prefect-worker -n prefect

# Check worker pods after restart
kubectl get pods -l app=prefect-worker -n prefect

# Check worker logs
kubectl logs -l app=prefect-worker -n prefect --tail=50 --follow
```

**Expected Behavior:**
- Worker restarts and reconnects to Prefect server
- Worker logs show successful connection
- Worker appears as active in Prefect UI

### 3.2 Redeploy Prefect Flow

**Via Prefect Integration Service:**
```bash
# Redeploy flow for a scheduled ingestion
curl -X POST http://prefect-integration-service:8084/deployments/sync \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_ingestion_id": "<scheduled-ingestion-id>",
    "tenant_id": "<tenant-id>"
  }'
```

**Via Hub API (if sync endpoint exists):**
```bash
# Trigger deployment sync via hub API
curl -X POST "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/sync-deployment/" \
  -H "Authorization: Bearer <token>"
```

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Deployments** section
3. Find deployment: `scheduled_ingestion_full_flow/<tenant-id>-<scheduled-ingestion-id>`
4. Click **Run** or **Edit** → **Update** to redeploy

**Via Prefect CLI:**
```bash
# Redeploy deployment (requires deployment name)
docker-compose exec prefect-worker prefect deployment run \
  "scheduled_ingestion_full_flow/<tenant-id>-<scheduled-ingestion-id>"
```

**Expected Behavior:**
- Deployment is updated/created in Prefect
- Flow code is reloaded
- Schedule is synced from hub configuration
- Deployment appears in Prefect UI

---

## 4. Handle Stuck Runs

### 4.1 Detect Stuck Runs

**Definition:** A run is considered "stuck" if it has been in `RUNNING` status for longer than the threshold (default: 2 hours).

**Via Prometheus Alert:**
- Alert `ScheduledIngestionRunStuck` triggers when `scheduled_ingestion_runs_running > 0` for 2 hours
- Check Prometheus alerts: `http://localhost:9090/alerts`
- Alert description includes remediation steps

**Via Database Query:**
```sql
-- Find stuck runs (RUNNING for > 2 hours)
SELECT
    id AS run_id,
    scheduled_ingestion_id,
    status,
    prefect_flow_run_id,
    started_at,
    NOW() - started_at AS running_duration,
    files_found,
    files_processed,
    files_failed
FROM scheduled_ingestion_scheduledingestionrun
WHERE status = 'RUNNING'
  AND started_at < NOW() - INTERVAL '2 hours'
ORDER BY started_at ASC;
```

**Via Hub API:**
```bash
# Query runs by status and time (requires API access)
curl -H "Authorization: Bearer <token>" \
  "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/runs/?status=RUNNING"
```

**Via Django Shell:**
```python
from django.utils import timezone
from datetime import timedelta
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

# Find stuck runs (RUNNING for > 2 hours)
threshold = timezone.now() - timedelta(hours=2)
stuck_runs = ScheduledIngestionRun.objects.filter(
    status='RUNNING',
    started_at__lt=threshold
).order_by('started_at')

for run in stuck_runs:
    duration = timezone.now() - run.started_at
    print(f"Run ID: {run.id}")
    print(f"  Prefect Flow Run ID: {run.prefect_flow_run_id}")
    print(f"  Started At: {run.started_at}")
    print(f"  Running Duration: {duration}")
    print(f"  Files Found: {run.files_found}")
    print(f"  Files Processed: {run.files_processed}")
    print()
```

### 4.2 Remediate Stuck Runs

**Step 1: Check Prefect Flow Run Status**

```bash
# Get Prefect flow run status
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/flow_runs/<prefect-flow-run-id>"
```

**Step 2: Determine Root Cause**

- **Prefect flow run is CANCELLED/FAILED but hub run is RUNNING:**
  - Hub run status is stale; update hub run to match Prefect status
- **Prefect flow run is RUNNING but no progress:**
  - Flow may be stuck; cancel Prefect flow run and mark hub run as FAILED
- **Prefect flow run does not exist:**
  - Hub run was created but Prefect flow never started; mark hub run as FAILED

**Step 3: Update Hub Run Status**

**Via Hub Internal API (Worker API):**
```bash
# Mark run as FAILED (requires HUB_WORKER_API_KEY)
curl -X PATCH "$HUB_BASE_URL/api/v1/scheduled-ingestions/internal/runs/<run-id>/" \
  -H "Authorization: ApiKey $HUB_WORKER_API_KEY" \
  -H "X-Tenant-ID: <tenant-id>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "FAILED",
    "error_message": "Run stuck in RUNNING status for > 2 hours; marked as FAILED by operator",
    "completed_at": "<current-timestamp>"
  }'
```

**Via Django Shell:**
```python
from django.utils import timezone
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

run = ScheduledIngestionRun.objects.get(id='<run-id>')
run.status = 'FAILED'
run.error_message = 'Run stuck in RUNNING status for > 2 hours; marked as FAILED by operator'
run.completed_at = timezone.now()
run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])

print(f"Run {run.id} marked as FAILED")
```

**Step 4: Cancel Prefect Flow Run (if still running)**

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Flow Runs** section
3. Find flow run by ID
4. Click **Cancel** button

**Via Prefect API:**
```bash
# Cancel flow run
curl -X POST "$PREFECT_API_URL/flow_runs/<flow-run-id>/cancel" \
  -H "Authorization: Bearer $PREFECT_API_KEY"
```

**Step 5: Verify Remediation**

```sql
-- Verify run status updated
SELECT id, status, completed_at, error_message
FROM scheduled_ingestion_scheduledingestionrun
WHERE id = '<run-id>';
```

### 4.3 Automated Stuck Run Detection (Optional)

**Periodic Job Script:**
```python
#!/usr/bin/env python3
"""
Periodic job to detect and remediate stuck runs.
Run via cron or scheduled task (e.g., every 30 minutes).
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun
import requests

STUCK_THRESHOLD_HOURS = int(os.getenv('STUCK_RUN_THRESHOLD_HOURS', '2'))
PREFECT_API_URL = os.getenv('PREFECT_API_URL', 'http://prefect-server:4200/api')
PREFECT_API_KEY = os.getenv('PREFECT_API_KEY', '')

def check_prefect_flow_run_status(prefect_flow_run_id: str):
    """Check Prefect flow run status."""
    if not prefect_flow_run_id:
        return None

    headers = {}
    if PREFECT_API_KEY:
        headers['Authorization'] = f'Bearer {PREFECT_API_KEY}'

    try:
        url = f"{PREFECT_API_URL}/flow_runs/{prefect_flow_run_id}"
        resp = requests.get(url, headers=headers, timeout=5)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Failed to check Prefect flow run {prefect_flow_run_id}: {e}")
        return None

def remediate_stuck_runs():
    """Detect and remediate stuck runs."""
    threshold = timezone.now() - timedelta(hours=STUCK_THRESHOLD_HOURS)
    stuck_runs = ScheduledIngestionRun.objects.filter(
        status='RUNNING',
        started_at__lt=threshold
    )

    for run in stuck_runs:
        print(f"Checking stuck run: {run.id} (Prefect flow_run_id: {run.prefect_flow_run_id})")

        # Check Prefect flow run status
        prefect_run = check_prefect_flow_run_status(run.prefect_flow_run_id) if run.prefect_flow_run_id else None

        if prefect_run:
            prefect_status = prefect_run.get('state_type', '').upper()
            print(f"  Prefect flow run status: {prefect_status}")

            # If Prefect flow is CANCELLED/FAILED, update hub run
            if prefect_status in ('CANCELLED', 'FAILED'):
                run.status = 'FAILED' if prefect_status == 'FAILED' else 'CANCELLED'
                run.error_message = f'Prefect flow run {prefect_status.lower()}; hub run status updated'
                run.completed_at = timezone.now()
                run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
                print(f"  ✅ Updated hub run {run.id} to {run.status}")
        else:
            # Prefect flow run not found or unreachable; mark hub run as FAILED
            run.status = 'FAILED'
            run.error_message = f'Stuck run detected (RUNNING > {STUCK_THRESHOLD_HOURS}h); Prefect flow run not found or unreachable'
            run.completed_at = timezone.now()
            run.save(update_fields=['status', 'error_message', 'completed_at', 'updated_at'])
            print(f"  ✅ Marked hub run {run.id} as FAILED (Prefect flow run not found)")

if __name__ == '__main__':
    remediate_stuck_runs()
```

**Cron Configuration:**
```bash
# Run every 30 minutes
*/30 * * * * /path/to/remediate_stuck_runs.py >> /var/log/stuck_runs.log 2>&1
```

---

## 5. Handle Failed Runs

### 5.1 Investigate Failed Runs

**Via Hub API:**
```bash
# Get failed runs
curl -H "Authorization: Bearer <token>" \
  "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/runs/?status=FAILED"
```

**Via Database Query:**
```sql
-- Find failed runs
SELECT
    id AS run_id,
    scheduled_ingestion_id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    error_message,
    files_found,
    files_processed,
    files_failed,
    result_json
FROM scheduled_ingestion_scheduledingestionrun
WHERE status = 'FAILED'
ORDER BY completed_at DESC
LIMIT 10;
```

**Via Django Shell:**
```python
from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

failed_runs = ScheduledIngestionRun.objects.filter(
    status='FAILED'
).order_by('-completed_at')[:10]

for run in failed_runs:
    print(f"Run ID: {run.id}")
    print(f"  Prefect Flow Run ID: {run.prefect_flow_run_id}")
    print(f"  Error: {run.error_message}")
    print(f"  Files Found: {run.files_found}")
    print(f"  Files Processed: {run.files_processed}")
    print(f"  Files Failed: {run.files_failed}")
    print(f"  Result JSON: {run.result_json}")
    print()
```

### 5.2 Check Prefect Flow Run Logs

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Flow Runs** section
3. Find flow run by ID (from `prefect_flow_run_id`)
4. Click on flow run to view details
5. Check **Logs** tab for error messages

**Via Prefect API:**
```bash
# Get flow run logs
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/flow_runs/<flow-run-id>/logs"
```

### 5.3 Common Failure Causes and Remediation

**1. Hub API Connection Failure**
- **Symptoms:** Worker cannot reach hub API, 401/403 errors
- **Remediation:**
  - Verify `HUB_BASE_URL` and `HUB_WORKER_API_KEY` are set correctly
  - Check network connectivity between worker and hub
  - Verify API key has correct scope (`scheduled_ingestion:internal`)

**2. Source Connector Failure**
- **Symptoms:** File discovery/download fails, connector errors in Prefect logs
- **Remediation:**
  - Check source credentials (S3, GCS, Azure Blob, etc.)
  - Verify source path/URL is accessible
  - Check network connectivity to source

**3. File Processing Failure**
- **Symptoms:** Files found but processing fails, DQ/compliance errors
- **Remediation:**
  - Check file format and size limits
  - Review DQ/compliance rules
  - Check hub API logs for processing errors

**4. Prefect Flow Timeout**
- **Symptoms:** Flow run times out, no completion
- **Remediation:**
  - Increase flow timeout if needed
  - Check for long-running file processing
  - Consider splitting large ingestion into smaller batches

### 5.4 Retry Failed Run

**Via Hub API (Manual Trigger):**
```bash
# Trigger scheduled ingestion manually
curl -X POST "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/trigger/" \
  -H "Authorization: Bearer <token>"
```

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Deployments** section
3. Find deployment
4. Click **Run** to trigger new flow run

---

## 6. Rollback Procedures

### 6.1 Rollback to django-rq Path (if feature flag exists)

**Note:** This procedure is only applicable if the django-rq path is kept behind a feature flag. If django-rq path is completely removed (Phase 3), this rollback is not possible.

**Step 1: Enable Feature Flag**

**Via Environment Variable:**
```bash
# Set feature flag to use django-rq
export USE_PREFECT_FOR_SCHEDULED_INGESTION=false

# Restart hub service
docker-compose restart api-service
```

**Via Django Settings:**
```python
# In hub/settings.py or environment-specific config
USE_PREFECT_FOR_SCHEDULED_INGESTION = False
```

**Step 2: Verify Rollback**

```bash
# Check feature flag is set
docker-compose exec api-service python -c \
  "from django.conf import settings; print(settings.USE_PREFECT_FOR_SCHEDULED_INGESTION)"

# Trigger scheduled ingestion and verify django-rq job is enqueued
curl -X POST "$HUB_BASE_URL/api/v1/scheduled-ingestions/<scheduled-ingestion-id>/trigger/" \
  -H "Authorization: Bearer <token>"

# Check RQ queue for job
docker-compose exec redis redis-cli LLEN job_default
```

**Step 3: Monitor Rollback**

- Monitor RQ worker logs for job processing
- Verify scheduled ingestion runs complete successfully
- Check metrics for django-rq job processing

### 6.2 Rollback Prefect Worker Deployment

**Docker Compose:**
```bash
# Rollback to previous worker image
docker-compose pull prefect-worker
docker-compose up -d prefect-worker

# Or use specific image tag
docker-compose up -d --no-deps prefect-worker --image prefecthq/prefect:2-python3.12@<digest>
```

**Kubernetes:**
```bash
# Rollback worker deployment
kubectl rollout undo deployment/prefect-worker -n prefect

# Check rollout status
kubectl rollout status deployment/prefect-worker -n prefect

# View rollout history
kubectl rollout history deployment/prefect-worker -n prefect
```

### 6.3 Rollback Hub API Changes

**Via Git/Docker Image:**
```bash
# Rollback to previous hub API image
docker-compose pull api-service
docker-compose up -d api-service

# Or use specific image tag
docker-compose up -d --no-deps api-service --image hub-api:<previous-tag>
```

**Kubernetes:**
```bash
# Rollback hub API deployment
kubectl rollout undo deployment/api-service -n default

# Check rollout status
kubectl rollout status deployment/api-service -n default
```

---

## 7. Validation & Recovery

### 7.1 Verify Worker Health

```bash
# Check worker container/pod status
docker-compose ps prefect-worker
# or
kubectl get pods -l app=prefect-worker -n prefect

# Check worker logs for errors
docker-compose logs prefect-worker --tail=100 | grep -i error
# or
kubectl logs -l app=prefect-worker -n prefect --tail=100 | grep -i error

# Verify worker connectivity
docker-compose exec prefect-worker prefect worker status
```

### 7.2 Verify Run Status

```sql
-- Check recent runs
SELECT
    id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    files_processed,
    files_failed
FROM scheduled_ingestion_scheduledingestionrun
WHERE scheduled_ingestion_id = '<scheduled-ingestion-id>'
ORDER BY created_at DESC
LIMIT 10;
```

### 7.3 Verify Metrics

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep scheduled_ingestion

# Verify alerts are not firing
curl http://localhost:9090/api/v1/alerts | jq '.data[] | select(.labels.alertname == "ScheduledIngestionRunStuck")'
```

---

## 8. Communication

### Internal Notifications

**Slack/Teams Channel:**
```
🔧 Scheduled Ingestion Operations
Action: <restart-worker|remediate-stuck-run|rollback>
Scheduled Ingestion ID: <id>
Run ID: <run-id> (if applicable)
Status: <in-progress|completed|failed>
Operator: @username
```

---

## 9. Post-Incident Actions

### After Remediation

- ✅ Document incident in runbook log
- ✅ Update runbook if gaps found
- ✅ Verify metrics return to normal
- ✅ Monitor for recurrence

### After Rollback

- ✅ Document rollback reason
- ✅ Create follow-up ticket for fix
- ✅ Verify system stability
- ✅ Plan re-deployment after fix

---

## Related Runbooks

- `RB-DEPLOY-001`: Standard Deployment Procedure
- `docs/RUNBOOKS.md`: Scheduled Ingestion Failures
- `docs/RUNBOOKS.md`: Prefect Workers Issues
- `docs/RUNBOOKS.md`: Prefect Server Issues

---

## Appendix

### Quick Reference Commands

```bash
# Check worker status
docker-compose ps prefect-worker
docker-compose logs prefect-worker --tail=50

# Restart worker
docker-compose restart prefect-worker

# Find stuck runs (SQL)
psql -U hub_user -d hub_db -c \
  "SELECT id, status, started_at, prefect_flow_run_id \
   FROM scheduled_ingestion_scheduledingestionrun \
   WHERE status = 'RUNNING' AND started_at < NOW() - INTERVAL '2 hours';"

# Correlate runs (Python)
python correlate_runs.py <prefect-flow-run-id>

# Redeploy flow
curl -X POST http://prefect-integration-service:8084/deployments/sync \
  -H "Content-Type: application/json" \
  -d '{"scheduled_ingestion_id": "<id>", "tenant_id": "<tenant-id>"}'
```

### Common Issues Checklist

- [ ] Worker container/pod is running
- [ ] Worker connected to Prefect server
- [ ] Work pool exists and is active
- [ ] Hub API connectivity from worker
- [ ] `HUB_WORKER_API_KEY` is set and valid
- [ ] Prefect flow deployments exist
- [ ] Runs are not stuck (RUNNING > 2h)
- [ ] Metrics are reporting correctly
- [ ] Alerts are not firing
