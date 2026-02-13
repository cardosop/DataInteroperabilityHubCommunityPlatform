# Deployment Order: Scheduled Ingestion (Prefect Worker)

This document describes the deployment order for migrating scheduled ingestion from django-rq to Prefect worker execution (Option C).

**Last Updated:** 2026-02-02
**Version:** 1.0

---

## Overview

The migration to Prefect worker execution requires a specific deployment order to ensure zero downtime and proper rollback capability. This document outlines the step-by-step deployment procedure.

**Key Principle:** Deploy hub API changes first (with optional feature flag), then deploy Prefect flow and worker, then switch to new flow, and finally disable django-rq path.

---

## Deployment Order

### Phase 1: Deploy Hub API (New Worker API Endpoints)

**Objective:** Deploy hub API with new internal Worker API endpoints while maintaining backward compatibility.

**Steps:**

1. **Deploy Hub API Service**
   ```bash
   # Docker Compose
   docker-compose pull api-service
   docker-compose up -d api-service

   # Kubernetes
   kubectl set image deployment/api-service api-service=hub-api:<version> -n default
   kubectl rollout status deployment/api-service -n default
   ```

2. **Verify Hub API Health**
   ```bash
   # Check health endpoint
   curl http://localhost:8000/health

   # Verify new internal endpoints exist (should return 401 without auth, not 404)
   curl -X POST http://localhost:8000/api/v1/scheduled-ingestions/internal/runs/ \
     -H "Content-Type: application/json" \
     -d '{"scheduled_ingestion_id": "test"}'
   # Expected: 401 Unauthorized (not 404 Not Found)
   ```

3. **Verify Backward Compatibility**
   - Existing scheduled ingestion APIs continue to work
   - Existing scheduled ingestion runs continue via django-rq (if still enabled)
   - No breaking changes to public APIs

**Rollback:** If issues occur, rollback hub API deployment:
```bash
kubectl rollout undo deployment/api-service -n default
```

**Duration:** ~5-10 minutes

---

### Phase 2: Deploy Prefect Flow and Worker (Optional Feature Flag)

**Objective:** Deploy Prefect flow code and worker with optional feature flag for gradual rollout.

**Steps:**

1. **Deploy Prefect Integration Service**
   ```bash
   # Docker Compose
   docker-compose pull prefect-integration-service
   docker-compose up -d prefect-integration-service

   # Kubernetes
   kubectl set image deployment/prefect-integration-service \
     prefect-integration-service=hub-prefect-integration:<version> -n prefect
   kubectl rollout status deployment/prefect-integration-service -n prefect
   ```

2. **Deploy Prefect Worker**
   ```bash
   # Docker Compose
   docker-compose pull prefect-worker
   docker-compose up -d prefect-worker

   # Kubernetes
   kubectl set image deployment/prefect-worker \
     prefect-worker=prefecthq/prefect:2-python3.12 -n prefect
   kubectl rollout status deployment/prefect-worker -n prefect
   ```

3. **Verify Prefect Worker Status**
   ```bash
   # Check worker logs
   docker-compose logs prefect-worker --tail=50
   # or
   kubectl logs -l app=prefect-worker -n prefect --tail=50

   # Verify worker connected to Prefect server
   docker-compose exec prefect-worker prefect worker status
   ```

4. **Verify Work Pool**
   ```bash
   # Check work pool exists and has active workers
   docker-compose exec prefect-worker prefect work-pool inspect default
   ```

5. **Sync Prefect Deployments (Optional)**
   ```bash
   # Sync deployments for existing scheduled ingestions
   # This can be done manually or via API
   curl -X POST http://prefect-integration-service:8084/deployments/sync \
     -H "Content-Type: application/json" \
     -d '{"scheduled_ingestion_id": "<id>", "tenant_id": "<tenant-id>"}'
   ```

**Feature Flag (Optional):**
If gradual rollout is desired, set feature flag:
```bash
# Environment variable (Docker Compose)
export USE_PREFECT_FOR_SCHEDULED_INGESTION=false  # Start with false

# Kubernetes ConfigMap
kubectl create configmap scheduled-ingestion-config \
  --from-literal=USE_PREFECT_FOR_SCHEDULED_INGESTION=false \
  -n default
```

**Rollback:** If issues occur:
```bash
kubectl rollout undo deployment/prefect-worker -n prefect
kubectl rollout undo deployment/prefect-integration-service -n prefect
```

**Duration:** ~10-15 minutes

---

### Phase 3: Switch Deployment to New Flow

**Objective:** Switch scheduled ingestion execution from django-rq to Prefect flow.

**Steps:**

1. **Verify Prefect Worker is Healthy**
   ```bash
   # Check worker status
   docker-compose ps prefect-worker
   # or
   kubectl get pods -l app=prefect-worker -n prefect

   # Check worker logs for errors
   docker-compose logs prefect-worker --tail=100 | grep -i error
   ```

2. **Sync All Scheduled Ingestion Deployments**
   ```bash
   # Via Prefect Integration Service API (for each scheduled ingestion)
   # Or via Django management command if available
   python manage.py sync_prefect_deployments
   ```

3. **Enable Feature Flag (if using gradual rollout)**
   ```bash
   # Set feature flag to true
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=true

   # Restart hub API to pick up flag
   docker-compose restart api-service
   # or
   kubectl rollout restart deployment/api-service -n default
   ```

4. **Verify First Prefect Flow Run**
   - Wait for next scheduled run or trigger manually
   - Check Prefect UI for flow run status
   - Verify hub run is created via Worker API
   - Check run completes successfully

5. **Monitor Metrics**
   ```bash
   # Check Prometheus metrics
   curl http://localhost:8000/metrics | grep scheduled_ingestion

   # Verify no errors in alerts
   curl http://localhost:9090/api/v1/alerts | jq '.data[] | select(.labels.component == "scheduled-ingestion")'
   ```

**Rollback:** If issues occur:
```bash
# Disable feature flag
export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
docker-compose restart api-service
```

**Duration:** ~15-30 minutes (including monitoring)

---

### Phase 4: Disable django-rq Path

**Objective:** Remove django-rq execution path for scheduled ingestion (after Prefect path is stable).

**Steps:**

1. **Verify Prefect Path is Stable**
   - Monitor for at least 24 hours (or agreed period)
   - Verify all scheduled runs complete successfully
   - Check error rates are within acceptable limits
   - Verify no stuck runs

2. **Remove django-rq Handler (Code Change)**
   - Update `hub/apps/jobs/tasks.py` to remove/disable SCHEDULED_INGESTION handler
   - Ensure no code path enqueues SCHEDULED_INGESTION to django-rq
   - Deploy code change

3. **Deploy Updated Hub API**
   ```bash
   # Deploy hub API with django-rq path removed
   docker-compose pull api-service
   docker-compose up -d api-service
   # or
   kubectl set image deployment/api-service api-service=hub-api:<version> -n default
   kubectl rollout status deployment/api-service -n default
   ```

4. **Verify django-rq Path is Disabled**
   ```bash
   # Check RQ queue (should not have SCHEDULED_INGESTION jobs)
   docker-compose exec redis redis-cli LLEN rq:queue:job_default

   # Trigger scheduled ingestion and verify no RQ job enqueued
   curl -X POST http://localhost:8000/api/v1/scheduled-ingestions/<id>/trigger/ \
     -H "Authorization: Bearer <token>"

   # Verify Prefect flow run started instead
   # Check Prefect UI for new flow run
   ```

5. **Remove Feature Flag (if used)**
   ```bash
   # Remove feature flag from environment/config
   # Code should always use Prefect path now
   ```

**Rollback:** If issues occur:
- Re-enable django-rq handler code
- Redeploy hub API
- Set feature flag back to false (if used)

**Duration:** ~10-15 minutes

---

## Complete Deployment Timeline

| Phase | Duration | Rollback Window |
|-------|----------|-----------------|
| Phase 1: Hub API | 5-10 min | Immediate |
| Phase 2: Prefect Flow/Worker | 10-15 min | Immediate |
| Phase 3: Switch to Prefect | 15-30 min | 24 hours |
| Phase 4: Disable django-rq | 10-15 min | 24 hours |
| **Total** | **40-70 min** | **48 hours** |

---

## Pre-Deployment Checklist

- [ ] All tests passing (unit, integration, E2E)
- [ ] Code review completed and approved
- [ ] Prefect server is healthy and accessible
- [ ] Hub API is healthy
- [ ] Database migrations applied (if any)
- [ ] Environment variables configured (`HUB_WORKER_API_KEY`, `PREFECT_API_URL`, etc.)
- [ ] Monitoring dashboards ready
- [ ] Rollback plan documented
- [ ] Team notified of deployment

---

## Post-Deployment Validation

### Immediate (First 10 minutes)

- [ ] Hub API health check passes
- [ ] Prefect worker connected and healthy
- [ ] Work pool active with workers
- [ ] No error spikes in metrics
- [ ] No alerts firing

### Short-term (First hour)

- [ ] At least one scheduled ingestion run completes successfully via Prefect
- [ ] Hub run created and updated correctly
- [ ] Prefect flow_run_id correlated with hub run_id
- [ ] Files processed successfully
- [ ] Metrics reporting correctly

### Long-term (24 hours)

- [ ] All scheduled runs complete successfully
- [ ] No stuck runs detected
- [ ] Error rates within acceptable limits
- [ ] Performance metrics stable
- [ ] No rollback needed

---

## Rollback Procedures

### Rollback Phase 4 (Disable django-rq)

If issues occur after disabling django-rq:

1. **Re-enable django-rq Handler**
   - Revert code change in `hub/apps/jobs/tasks.py`
   - Redeploy hub API

2. **Set Feature Flag (if used)**
   ```bash
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
   docker-compose restart api-service
   ```

3. **Verify Rollback**
   - Check RQ queue for SCHEDULED_INGESTION jobs
   - Verify runs complete via django-rq
   - Monitor for stability

### Rollback Phase 3 (Switch to Prefect)

If issues occur after switching to Prefect:

1. **Disable Feature Flag**
   ```bash
   export USE_PREFECT_FOR_SCHEDULED_INGESTION=false
   docker-compose restart api-service
   ```

2. **Verify django-rq Path Active**
   - Check RQ queue for jobs
   - Verify runs complete via django-rq

### Rollback Phase 2 (Prefect Flow/Worker)

If issues occur with Prefect worker:

1. **Rollback Worker Deployment**
   ```bash
   kubectl rollout undo deployment/prefect-worker -n prefect
   ```

2. **Rollback Integration Service**
   ```bash
   kubectl rollout undo deployment/prefect-integration-service -n prefect
   ```

### Rollback Phase 1 (Hub API)

If issues occur with hub API:

1. **Rollback Hub API**
   ```bash
   kubectl rollout undo deployment/api-service -n default
   ```

---

## Feature Flag Configuration

### Environment Variable

**Docker Compose:**
```yaml
services:
  api-service:
    environment:
      USE_PREFECT_FOR_SCHEDULED_INGESTION: "false"  # Start with false
```

**Kubernetes ConfigMap:**
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: scheduled-ingestion-config
  namespace: default
data:
  USE_PREFECT_FOR_SCHEDULED_INGESTION: "false"  # Start with false
```

### Django Settings

```python
# hub/settings.py
USE_PREFECT_FOR_SCHEDULED_INGESTION = env.bool(
    "USE_PREFECT_FOR_SCHEDULED_INGESTION", default=False
)
```

### Code Usage

```python
# hub/apps/scheduled_ingestion/views.py
from django.conf import settings

if settings.USE_PREFECT_FOR_SCHEDULED_INGESTION:
    # Use Prefect flow
    trigger_prefect_flow(...)
else:
    # Use django-rq (legacy)
    enqueue_scheduled_ingestion_job(...)
```

---

## Monitoring During Deployment

### Key Metrics to Watch

1. **Hub API Metrics**
   - `http_requests_total` (should remain stable)
   - `http_errors_total` (should not spike)
   - `scheduled_ingestion_runs_total` (should continue)

2. **Prefect Metrics**
   - Worker connection status
   - Flow run success rate
   - Flow run duration

3. **Scheduled Ingestion Metrics**
   - `scheduled_ingestion_runs_running` (should not have stuck runs)
   - `scheduled_ingestion_runs_total{status="FAILED"}` (should remain low)
   - `scheduled_ingestion_files_processed_total` (should continue)

### Alerts to Monitor

- `ScheduledIngestionRunStuck` (should not fire)
- `ScheduledIngestionNoRunsStarted` (should not fire during deployment)
- `ServiceDown` (should not fire)

---

## Release Notes Template

```markdown
## Scheduled Ingestion Migration to Prefect Worker

### Summary
Migrated scheduled ingestion execution from django-rq to Prefect worker (Option C).

### Changes
- Added internal Worker API endpoints for run lifecycle and process-file
- Deployed Prefect flow (`scheduled_ingestion_full_flow`) for scheduled ingestion
- Prefect worker now executes scheduled ingestion runs
- Removed django-rq execution path for scheduled ingestion

### Deployment Order
1. Hub API (new Worker API endpoints)
2. Prefect flow and worker
3. Switch to Prefect execution
4. Disable django-rq path

### Breaking Changes
- None (backward compatible during migration)

### Rollback
- Feature flag `USE_PREFECT_FOR_SCHEDULED_INGESTION` available for gradual rollout
- django-rq path can be re-enabled if needed (Phase 4 rollback)

### Documentation
- See `docs/DEPLOYMENT_ORDER_SCHEDULED_INGESTION.md` for deployment procedures
- See `runbooks/RB-SCHEDULED-INGESTION-001.md` for operational procedures
```

---

## Related Documentation

- `runbooks/RB-SCHEDULED-INGESTION-001.md`: Scheduled Ingestion Operations Runbook
- `runbooks/RB-DEPLOY-001.md`: Standard Deployment Procedure
- `docs/SCHEDULED_INGESTION_WORKER_API.md`: Worker API Documentation
- `docs/DOCKER_COMPOSE_DEPLOYMENT.md`: Docker Compose Deployment Guide
- `k8s/README.md`: Kubernetes Deployment Guide
