# Release Notes: Scheduled Ingestion Migration to Prefect Worker

**Version:** 1.0.0
**Release Date:** 2026-02-02
**Status:** Production Ready

---

## Summary

This release migrates scheduled ingestion execution from django-rq to Prefect worker (Option C). Scheduled ingestion runs are now executed by Prefect workers via the new Worker API, providing better scalability, observability, and reliability.

---

## Key Changes

### 1. New Worker API Endpoints

**Internal API for Prefect Workers:**
- `POST /api/v1/scheduled-ingestions/internal/runs/` - Create run (idempotent)
- `PATCH /api/v1/scheduled-ingestions/internal/runs/{run_id}/` - Update run status
- `POST /api/v1/scheduled-ingestions/internal/process-file/` - Process file for run
- `GET /api/v1/scheduled-ingestions/internal/config/{id}/` - Get config (credentials masked)

**Authentication:**
- Worker API key (`HUB_WORKER_API_KEY`) required
- Tenant isolation enforced
- Credentials masked in config responses and logs

### 2. Prefect Flow Implementation

**New Flow:** `scheduled_ingestion_full_flow`
- HTTP-only execution (no Django in worker)
- Full workflow: config → create run → discover → filter → process files → update run
- Handles cancellation/timeout: updates hub run status before exiting
- Correlates Prefect flow_run_id with hub run_id

### 3. Deployment Sync

**Prefect Integration Service:**
- Syncs scheduled ingestion configurations to Prefect deployments
- Creates/updates deployments with cron schedules
- Deployment name format: `{tenant_id}-{scheduled_ingestion_id}`

### 4. Removed django-rq Execution Path

**Breaking Change:**
- `SCHEDULED_INGESTION` jobs are no longer enqueued to django-rq
- RQ handler for `SCHEDULED_INGESTION` is disabled
- All scheduled ingestion runs execute via Prefect

---

## Deployment Order

See `docs/DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md` for detailed deployment procedures.

**Quick Summary:**
1. Deploy hub API (new Worker API endpoints)
2. Deploy Prefect flow and worker
3. Switch deployment to new flow (optional feature flag)
4. Disable django-rq path

---

## Feature Flag (Optional)

**Environment Variable:** `USE_PREFECT_FOR_SCHEDULED_INGESTION`

- **Default:** `false` (for gradual rollout)
- **Set to:** `true` to enable Prefect execution
- **Note:** If django-rq path is completely removed, this flag is not applicable

---

## Configuration

### Required Environment Variables

**Hub API:**
- `HUB_WORKER_API_KEY` - Worker API key for authentication

**Prefect Worker:**
- `HUB_BASE_URL` - Hub API base URL (e.g., `http://api-service:8000`)
- `HUB_WORKER_API_KEY` - Worker API key
- `PREFECT_API_URL` - Prefect API URL (e.g., `http://prefect-server:4200/api`)
- `PREFECT_WORKER_POOL` - Work pool name (default: `default`)

**Prefect Integration Service:**
- `PREFECT_API_URL` - Prefect API URL
- `PREFECT_API_KEY` - Prefect API key (optional)
- `PREFECT_DEPLOYMENT_IMAGE` - Docker image for deployments

### Docker Compose

See `docker-compose.yml` for Prefect worker configuration:
- Service: `prefect-worker`
- Volumes: `./services/prefect-integration:/app:ro`
- Environment: `HUB_BASE_URL`, `HUB_WORKER_API_KEY`, `PREFECT_API_URL`

### Kubernetes

See `k8s/prefect-workers/base/` for Kubernetes configuration:
- ConfigMap: `prefect-worker-config`
- Secret: `prefect-worker-secrets`
- Deployment: `prefect-worker`

---

## Operational Procedures

### Runbooks

- **RB-SCHEDULED-INGESTION-001**: Scheduled Ingestion Operations (Prefect Worker)
  - Verify Prefect worker and pool
  - Correlate Prefect flow_run_id with hub run_id
  - Restart worker and redeploy flow
  - Handle stuck runs and failed runs
  - Rollback procedures

### Management Commands

**Detect and Remediate Stuck Runs:**
```bash
python manage.py detect_and_remediate_stuck_runs
python manage.py detect_and_remediate_stuck_runs --threshold-hours 3
python manage.py detect_and_remediate_stuck_runs --dry-run
```

**Cron Configuration (Optional):**
```bash
# Run every 30 minutes
*/30 * * * * /path/to/manage.py detect_and_remediate_stuck_runs
```

---

## Monitoring and Observability

### Prometheus Metrics

**Run Metrics:**
- `scheduled_ingestion_runs_total` - Total runs by status
- `scheduled_ingestion_runs_running` - Currently running runs
- `scheduled_ingestion_duration_seconds` - Run duration histogram

**File Metrics:**
- `scheduled_ingestion_files_processed_total` - Files processed
- `scheduled_ingestion_files_failed_total` - Files failed
- `scheduled_ingestion_files_per_run` - Files per run histogram

**Ingestion Metrics:**
- `scheduled_ingestion_active_count` - Active ingestions
- `scheduled_ingestion_datasets_created_total` - Datasets created

### Alerts

**Stuck Run Alert:**
- **Name:** `ScheduledIngestionRunStuck`
- **Trigger:** Run in RUNNING status > 2 hours
- **Severity:** High
- **Remediation:** See runbook RB-SCHEDULED-INGESTION-001

**No Runs Started Alert:**
- **Name:** `ScheduledIngestionNoRunsStarted`
- **Trigger:** Active ingestions but no runs started in last hour
- **Severity:** Medium
- **Remediation:** Check Prefect worker and deployment sync

### Grafana Dashboard

**Dashboard:** `monitoring/grafana/dashboards/scheduled-ingestion.json`

**Panels:**
- Active scheduled ingestions
- Runs by status
- Run rate over time
- Files processed/failed
- Currently running runs
- Stuck runs alert
- Prefect worker status
- Runs with Prefect flow_run_id correlation

---

## Breaking Changes

### Removed django-rq Execution

- `SCHEDULED_INGESTION` jobs are no longer enqueued to django-rq
- RQ handler for `SCHEDULED_INGESTION` is disabled
- All scheduled ingestion runs execute via Prefect

**Migration Path:**
- Existing scheduled ingestions are automatically synced to Prefect deployments
- Manual trigger via API starts Prefect flow run (not RQ job)
- Run status and history remain in hub database

### API Changes

**New Internal Endpoints:**
- Worker-only endpoints under `/api/v1/scheduled-ingestions/internal/`
- Require worker API key authentication
- Not exposed in public API docs

**Public API:**
- No breaking changes to public scheduled ingestion APIs
- Run status and history APIs unchanged
- Prefect flow_run_id included in run responses

---

## Rollback Procedures

### Rollback to django-rq (if feature flag exists)

1. Set `USE_PREFECT_FOR_SCHEDULED_INGESTION=false`
2. Restart hub API service
3. Verify RQ jobs are enqueued
4. Monitor for stability

**Note:** If django-rq path is completely removed (Phase 4), rollback requires code change.

### Rollback Prefect Worker

1. Rollback worker deployment:
   ```bash
   kubectl rollout undo deployment/prefect-worker -n prefect
   ```
2. Verify worker reconnects
3. Monitor for stability

---

## Testing

### Test Coverage

- Unit tests for Worker API endpoints
- Integration tests for full flow execution
- E2E tests for scheduled ingestion journey
- Tests use real services (no mocks)

### Test Execution

```bash
# Run Phase 7 comprehensive tests
pytest hub/apps/scheduled_ingestion/tests/test_phase7_comprehensive.py -v

# Run Prefect integration tests
pytest services/prefect-integration/tests/ -v

# Run E2E tests
pytest tests/e2e/test_scheduled_ingestion.py -v
```

---

## Documentation

### New Documentation

- `docs/DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md` - Deployment procedures
- `runbooks/RB-SCHEDULED-INGESTION-001.md` - Operational runbook
- `docs/SCHEDULED_INGESTION_WORKER_API.md` - Worker API documentation

### Updated Documentation

- `docs/RUNBOOKS.md` - Added scheduled ingestion runbook reference
- `docs/DOCKER_COMPOSE_DEPLOYMENT.md` - Prefect worker configuration
- `k8s/README.md` - Kubernetes Prefect worker setup
- `services/prefect-integration/README.md` - Prefect integration service

---

## Known Issues

None at this time.

---

## Support

For issues or questions:
- See runbook: `runbooks/RB-SCHEDULED-INGESTION-001.md`
- Check logs: `docker-compose logs prefect-worker`
- Review metrics: Grafana dashboard `Scheduled Ingestion`
- Check alerts: Prometheus alerts `ScheduledIngestionRunStuck`, `ScheduledIngestionNoRunsStarted`

---

## Related Issues/PRs

- Phase 1-7: Prefect Work Pools as Execution Layer for Scheduled Ingestion
- Phase 8: Ops and CI/CD (this release)

---

## Contributors

- Platform Team
- SRE Team
