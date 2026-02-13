# RB-SCHEDULED-EXPORT-001: Scheduled Export Operations (Prefect Worker)

**Runbook ID:** `RB-SCHEDULED-EXPORT-001`
**Title:** Scheduled Export Operations (Prefect Worker)
**Last Updated:** 2026-02-03
**Version:** 1.0

---

## Scope

This runbook covers operational procedures for scheduled export using Prefect workers. It includes verification, troubleshooting, remediation, and rollback procedures.

**In Scope:**
- Verifying Prefect worker and pool status
- Correlating Prefect flow_run_id with hub run_id
- Restarting workers and redeploying flows
- Handling stuck runs and failed runs
- Rollback procedures

**Out of Scope:**
- Initial setup and configuration (see `docs/DOCKER_COMPOSE_DEPLOYMENT.md` and `k8s/README.md`)
- Prefect server issues (see `docs/RUNBOOKS.md` - Prefect Server Issues)
- General scheduled export failures (see `docs/RUNBOOKS.md` - Scheduled Export Failures)

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
   http://api-service:8000/api/v1/scheduled-exports/internal/config/<scheduled-export-id>/'
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
  "$HUB_BASE_URL/api/v1/scheduled-exports/<scheduled-export-id>/runs/?prefect_flow_run_id=<flow-run-id>"
```

**Via Database Query:**
```sql
-- Find hub run by Prefect flow_run_id
SELECT
    id AS hub_run_id,
    scheduled_export_id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    items_exported,
    items_failed
FROM scheduled_export_scheduledexportrun
WHERE prefect_flow_run_id = '<prefect-flow-run-id>';
```

**Via Django Shell:**
```python
from hub.apps.scheduled_export.models import ScheduledExportRun

# Find run by Prefect flow_run_id
run = ScheduledExportRun.objects.filter(
    prefect_flow_run_id='<prefect-flow-run-id>'
).first()

if run:
    print(f"Hub Run ID: {run.id}")
    print(f"Scheduled Export ID: {run.scheduled_export_id}")
    print(f"Status: {run.status}")
    print(f"Started At: {run.started_at}")
    print(f"Completed At: {run.completed_at}")
    print(f"Items Exported: {run.items_exported}")
    print(f"Items Failed: {run.items_failed}")
else:
    print("No hub run found for this Prefect flow_run_id")
```

### 2.2 Find Prefect Flow Run by Hub run_id

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Flow Runs** section
3. Search by flow name: `scheduled_export_full_flow`
4. Filter by tags or parameters to find matching run

**Via Prefect API:**
```bash
# Get flow runs (requires PREFECT_API_KEY)
curl -H "Authorization: Bearer $PREFECT_API_KEY" \
  "$PREFECT_API_URL/flow_runs/?flow_name=scheduled_export_full_flow"

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
WHERE parameters->>'scheduled_export_id' = '<scheduled-export-id>'
  AND start_time >= '<start-time-filter>';
```

### 2.3 Correlation Verification Script

**Python Script:**
```python
#!/usr/bin/env python3
"""
Correlate Prefect flow_run_id with Hub run_id.
Usage: python correlate_export_runs.py <prefect-flow-run-id> [--hub-run-id <hub-run-id>]
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

def get_hub_run_by_prefect_id(prefect_flow_run_id: str, scheduled_export_id: str):
    """Get Hub run by Prefect flow_run_id."""
    headers = {}
    if HUB_API_KEY:
        headers["Authorization"] = f"Bearer {HUB_API_KEY}"

    url = f"{HUB_BASE_URL}/api/v1/scheduled-exports/{scheduled_export_id}/runs/"
    params = {"prefect_flow_run_id": prefect_flow_run_id}
    resp = requests.get(url, headers=headers, params=params)
    resp.raise_for_status()
    return resp.json()

def correlate_runs(prefect_flow_run_id: str):
    """Correlate Prefect flow run with Hub run."""
    print(f"Fetching Prefect flow run: {prefect_flow_run_id}")
    prefect_run = get_prefect_flow_run(prefect_flow_run_id)

    scheduled_export_id = prefect_run.get("parameters", {}).get("scheduled_export_id")
    if not scheduled_export_id:
        print("ERROR: Prefect flow run does not have scheduled_export_id in parameters")
        return

    print(f"Scheduled Export ID: {scheduled_export_id}")
    print(f"Prefect Flow Run Status: {prefect_run.get('state_type')}")
    print(f"Prefect Flow Run Name: {prefect_run.get('name')}")

    print(f"\nFetching Hub run for Prefect flow_run_id: {prefect_flow_run_id}")
    hub_runs = get_hub_run_by_prefect_id(prefect_flow_run_id, scheduled_export_id)

    if hub_runs.get("results"):
        hub_run = hub_runs["results"][0]
        print(f"\n✅ Correlation Found:")
        print(f"  Hub Run ID: {hub_run['id']}")
        print(f"  Hub Run Status: {hub_run['status']}")
        print(f"  Prefect Flow Run ID: {hub_run.get('prefect_flow_run_id')}")
        print(f"  Started At: {hub_run.get('started_at')}")
        print(f"  Completed At: {hub_run.get('completed_at')}")
        print(f"  Items Exported: {hub_run.get('items_exported', 0)}")
        print(f"  Items Failed: {hub_run.get('items_failed', 0)}")
    else:
        print(f"\n⚠️  No Hub run found for Prefect flow_run_id: {prefect_flow_run_id}")
        print("  This may indicate:")
        print("  - Hub run was not created (check Prefect flow logs)")
        print("  - prefect_flow_run_id was not set in hub run")
        print("  - Hub API call failed during flow execution")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python correlate_export_runs.py <prefect-flow-run-id>")
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
# Redeploy flow for a scheduled export
curl -X POST http://prefect-integration-service:8084/deployments/sync \
  -H "Content-Type: application/json" \
  -d '{
    "scheduled_export_id": "<scheduled-export-id>",
    "tenant_id": "<tenant-id>"
  }'
```

**Via Hub API (if sync endpoint exists):**
```bash
# Trigger deployment sync via hub API
curl -X POST "$HUB_BASE_URL/api/v1/scheduled-exports/<scheduled-export-id>/sync-deployment/" \
  -H "Authorization: Bearer <token>"
```

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Deployments** section
3. Find deployment: `scheduled_export_full_flow/<tenant-id>-<scheduled-export-id>`
4. Click **Run** or **Edit** → **Update** to redeploy

**Via Prefect CLI:**
```bash
# Redeploy deployment (requires deployment name)
docker-compose exec prefect-worker prefect deployment run \
  "scheduled_export_full_flow/<tenant-id>-<scheduled-export-id>"
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
- Alert `ScheduledExportRunStuck` triggers when `scheduled_export_runs_running > 0` for 2 hours
- Check Prometheus alerts: `http://localhost:9090/alerts`
- Alert description includes remediation steps

**Via Database Query:**
```sql
-- Find stuck runs (RUNNING for > 2 hours)
SELECT
    id AS run_id,
    scheduled_export_id,
    status,
    prefect_flow_run_id,
    started_at,
    NOW() - started_at AS running_duration,
    items_exported,
    items_failed
FROM scheduled_export_scheduledexportrun
WHERE status = 'RUNNING'
  AND started_at < NOW() - INTERVAL '2 hours'
ORDER BY started_at ASC;
```

**Via Hub API:**
```bash
# Query runs by status and time (requires API access)
curl -H "Authorization: Bearer <token>" \
  "$HUB_BASE_URL/api/v1/scheduled-exports/<scheduled-export-id>/runs/?status=RUNNING"
```

**Via Django Shell:**
```python
from django.utils import timezone
from datetime import timedelta
from hub.apps.scheduled_export.models import ScheduledExportRun

# Find stuck runs (RUNNING for > 2 hours)
threshold = timezone.now() - timedelta(hours=2)
stuck_runs = ScheduledExportRun.objects.filter(
    status='RUNNING',
    started_at__lt=threshold
).order_by('started_at')

for run in stuck_runs:
    duration = timezone.now() - run.started_at
    print(f"Run ID: {run.id}")
    print(f"  Prefect Flow Run ID: {run.prefect_flow_run_id}")
    print(f"  Started At: {run.started_at}")
    print(f"  Running Duration: {duration}")
    print(f"  Items Exported: {run.items_exported}")
    print(f"  Items Failed: {run.items_failed}")
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
curl -X PATCH "$HUB_BASE_URL/api/v1/scheduled-exports/internal/runs/<run-id>/" \
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
from hub.apps.scheduled_export.models import ScheduledExportRun, ScheduledExportRunStatus

# Find stuck run
run = ScheduledExportRun.objects.get(id='<run-id>')

# Update status to FAILED
run.status = ScheduledExportRunStatus.FAILED
run.error_message = "Run stuck in RUNNING status for > 2 hours; marked as FAILED by operator"
run.completed_at = timezone.now()
run.save()

print(f"Run {run.id} marked as FAILED")
```

**Step 4: Cancel Prefect Flow Run (if still running)**

```bash
# Cancel Prefect flow run
curl -X POST "$PREFECT_API_URL/flow_runs/<prefect-flow-run-id>/cancel" \
  -H "Authorization: Bearer $PREFECT_API_KEY"
```

---

## 5. Handle Failed Runs

### 5.1 Investigate Failed Runs

**Via Hub API:**
```bash
# Get failed runs for a scheduled export
curl -H "Authorization: Bearer <token>" \
  "$HUB_BASE_URL/api/v1/scheduled-exports/<scheduled-export-id>/runs/?status=FAILED"
```

**Via Database Query:**
```sql
-- Find recent failed runs
SELECT
    id AS run_id,
    scheduled_export_id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    error_message,
    items_exported,
    items_failed
FROM scheduled_export_scheduledexportrun
WHERE status = 'FAILED'
  AND completed_at > NOW() - INTERVAL '24 hours'
ORDER BY completed_at DESC
LIMIT 10;
```

**Via Prefect UI:**
1. Navigate to Prefect UI
2. Go to **Flow Runs** section
3. Filter by status: `Failed`
4. Find flow run matching hub run_id
5. Review logs and error details

### 5.2 Common Failure Scenarios

**Scenario 1: Authentication Failure**
- **Symptoms:** Worker API returns 401/403
- **Remediation:** Verify `HUB_WORKER_API_KEY` is set correctly in worker environment
- **Prevention:** Use Prefect Blocks or secrets management for API keys

**Scenario 2: Destination Connection Failure**
- **Symptoms:** Export fails with connection error
- **Remediation:** Verify destination credentials (S3/GCS/Azure Blob) are valid
- **Prevention:** Test destination connectivity before creating scheduled export

**Scenario 3: Source Scope Validation Failure**
- **Symptoms:** Export fails with "no items found" or "access denied"
- **Remediation:** Verify source scope (asset_ids, dataset_ids, file_ids, contract_id) is valid and accessible
- **Prevention:** Validate source scope at creation time

**Scenario 4: Prefect Flow Execution Failure**
- **Symptoms:** Prefect flow run fails, hub run remains RUNNING
- **Remediation:** Check Prefect flow logs, update hub run status manually if needed
- **Prevention:** Implement proper error handling in Prefect flow

---

## 6. Validation & Recovery

### 6.1 Verify Worker Status After Remediation

```bash
# Check worker is running
docker-compose ps prefect-worker
# or
kubectl get pods -l app=prefect-worker -n prefect

# Verify worker is connected
docker-compose exec prefect-worker prefect worker status
```

### 6.2 Verify Run Status

```sql
-- Check recent runs
SELECT
    id,
    scheduled_export_id,
    status,
    prefect_flow_run_id,
    started_at,
    completed_at,
    items_exported,
    items_failed
FROM scheduled_export_scheduledexportrun
WHERE scheduled_export_id = '<scheduled-export-id>'
ORDER BY created_at DESC
LIMIT 10;
```

### 6.3 Verify Metrics

```bash
# Check Prometheus metrics
curl http://localhost:8000/metrics | grep scheduled_export

# Verify alerts are not firing
curl http://localhost:9090/api/v1/alerts | jq '.data[] | select(.labels.alertname == "ScheduledExportRunStuck")'
```

---

## 7. Communication

### Internal Notifications

**Slack/Teams Channel:**
```
🔧 Scheduled Export Operations
Action: <restart-worker|remediate-stuck-run|rollback>
Scheduled Export ID: <id>
Run ID: <run-id> (if applicable)
Status: <in-progress|completed|failed>
Operator: @username
```

---

## 8. Post-Incident Actions

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
- `RB-SCHEDULED-INGESTION-001`: Scheduled Ingestion Operations (similar procedures)
- `docs/RUNBOOKS.md`: Scheduled Export Failures
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
   FROM scheduled_export_scheduledexportrun \
   WHERE status = 'RUNNING' AND started_at < NOW() - INTERVAL '2 hours';"

# Correlate runs (Python)
python correlate_export_runs.py <prefect-flow-run-id>

# Redeploy flow
curl -X POST http://prefect-integration-service:8084/deployments/sync \
  -H "Content-Type: application/json" \
  -d '{"scheduled_export_id": "<id>", "tenant_id": "<tenant-id>"}'
```

### Common Issues Checklist

- [ ] Worker container/pod is running
- [ ] Worker connected to Prefect server
- [ ] Work pool exists and is active
- [ ] Hub API connectivity from worker
- [ ] `HUB_WORKER_API_KEY` is set and valid
- [ ] Destination credentials are valid
- [ ] Source scope is valid and accessible
- [ ] Prefect flow deployment exists
