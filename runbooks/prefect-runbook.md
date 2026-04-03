# Prefect Operations Runbook

Step-by-step procedures for the five most common Prefect-related failure
scenarios in the Meshant platform.

---

## (a) Schedule Active but Never Fires

**Symptom:** A scheduled ingestion or export has `status: ACTIVE` but no runs
appear and the cron never triggers.

**Root cause:** The Prefect deployment was not created or the sync failed.

**Diagnosis:**

1. Check `deployment_sync_status` on the resource:
   ```bash
   curl -s -H "Authorization: Bearer $TOKEN" \
     $API_URL/api/v1/scheduled-ingestions/$ID/ | jq '.deployment_sync_status'
   ```
2. If `FAILED` or `PENDING`, the Prefect deployment does not exist.

**Resolution:**

1. Call the sync retry endpoint:
   ```bash
   curl -X POST -H "Authorization: Bearer $TOKEN" \
     $API_URL/api/v1/scheduled-ingestions/$ID/sync/
   ```
2. Verify the response returns `deployment_sync_status: "SYNCED"`.
3. If sync fails again, check prefect-integration-service logs:
   ```bash
   kubectl logs -l app=prefect-integration-service --tail=100
   ```
4. Common causes:
   - `PREFECT_INTEGRATION_SERVICE_URL` misconfigured (must be port 8084, not 4200)
   - Prefect server unreachable from the integration service pod
   - `PREFECT_DEPLOYMENT_IMAGE` not set or image not pullable

---

## (b) Run Stuck in RUNNING

**Symptom:** A scheduled ingestion run shows `status: RUNNING` for hours with no
progress.

**Root cause:** The Prefect flow run's worker pod was OOM-killed, evicted, or the
flow errored in a way that never reported back to the hub.

**Diagnosis:**

1. Check the Prefect UI for the flow run status:
   ```
   $PREFECT_UI_URL/flow-runs/flow-run/$PREFECT_FLOW_RUN_ID
   ```
2. If the flow run shows FAILED/CRASHED in Prefect but RUNNING in the hub,
   the status was never synced back.

**Resolution:**

1. Run the reconciliation management command:
   ```bash
   kubectl exec -it deploy/api -- python manage.py reconcile_prefect_statuses
   ```
   This checks each RUNNING hub run against Prefect and updates the hub status
   to match.

2. Alternatively, wait for the `recover_stuck_jobs` CronJob (runs every 15 min)
   or the `detect_and_remediate_stuck_runs` CronJob (runs hourly) to
   automatically mark the run as FAILED after the threshold (default: 2 hours).

3. If urgency requires immediate resolution:
   ```bash
   kubectl exec -it deploy/api -- python manage.py recover_stuck_jobs \
     --threshold-minutes 30
   ```

---

## (c) Prefect-Integration-Service Circuit Open

**Symptom:** Deployment sync/trigger calls return HTTP 503 with a `Retry-After`
header.  Logs show `circuit_breaker_open`.

**Root cause:** The circuit breaker opened after consecutive failures to the
Prefect server API (connection refused, timeouts, 5xx errors).

**Diagnosis:**

1. Check the `/metrics` endpoint on the integration service:
   ```bash
   curl -s http://prefect-integration-service:8084/metrics | \
     grep prefect_circuit_breaker
   ```
2. Look for `prefect_circuit_breaker_state{circuit="..."}` gauge:
   - `0` = CLOSED (healthy)
   - `1` = OPEN (rejecting calls)

**Resolution:**

1. **Wait 30 seconds** — the circuit auto-resets to half-open after the
   cooldown period and will probe the next request.
2. If the Prefect server is actually down, fix it first:
   ```bash
   kubectl get pods -l app=prefect-server
   kubectl logs -l app=prefect-server --tail=50
   ```
3. If the circuit remains open after the Prefect server is healthy, restart the
   integration service pod to reset state:
   ```bash
   kubectl rollout restart deploy/prefect-integration-service
   ```

---

## (d) Worker Not Picking Jobs from Pool

**Symptom:** Deployments are SYNCED, flow runs are SCHEDULED in Prefect, but no
worker picks them up and they stay in `SCHEDULED`/`PENDING` state.

**Root cause:** The Prefect worker process is not running, not connected to the
correct work pool, or the work pool is paused.

**Diagnosis:**

1. Inspect the work pool:
   ```bash
   kubectl exec -it deploy/prefect-worker -- \
     prefect work-pool inspect "kubernetes-pool"
   ```
2. Check if the pool is paused (`is_paused: true`).
3. Check worker pod status:
   ```bash
   kubectl get pods -l app=prefect-worker
   kubectl logs -l app=prefect-worker --tail=50
   ```
4. Verify the worker is polling the correct pool name (must match
   `PREFECT_WORK_POOL_NAME` in the integration service config).

**Resolution:**

1. If the pool is paused, resume it:
   ```bash
   prefect work-pool resume "kubernetes-pool"
   ```
2. If the worker pod is in CrashLoopBackOff, check its logs and fix the
   underlying issue (usually missing env vars or Prefect server connectivity).
3. If the pool name is mismatched, update the integration service config:
   ```bash
   kubectl set env deploy/prefect-integration-service \
     PREFECT_WORK_POOL_NAME=kubernetes-pool
   ```

---

## (e) Stale Deployment After Schedule Delete

**Symptom:** A scheduled ingestion/export was deleted from the hub, but its
Prefect deployment still exists and continues to fire flow runs.

**Root cause:** The delete endpoint calls the integration service to remove the
deployment before deleting the DB record.  If that call fails, the record is
soft-deleted (`status: DELETED`) but the Prefect deployment persists.

**Diagnosis:**

1. Check for orphaned deployments:
   ```bash
   kubectl exec -it deploy/api -- python manage.py \
     purge_orphan_prefect_deployments --dry-run
   ```
2. This lists Prefect deployments that have no matching hub record or whose hub
   record is in `DELETED` status.

**Resolution:**

1. Run the purge command (without `--dry-run`):
   ```bash
   kubectl exec -it deploy/api -- python manage.py \
     purge_orphan_prefect_deployments
   ```
2. This command:
   - Calls the integration service to delete each orphaned deployment
   - Clears `prefect_deployment_id` on the hub record
   - Hard-deletes any `DELETED`-status records whose deployment was removed

3. The purge CronJob runs hourly by default, so stale deployments are
   automatically cleaned up within an hour.
