# Production Deployment

Guide for deploying Meshant to production environments. Meshant runs on
AWS EKS and is deployed via Helm with image builds, Trivy scanning, and
cosign signing handled by the GitHub Actions `deploy.yml` workflow.

## Pre-Flight Checklist

- [ ] All CI checks green on the release branch (unit, integration, Trivy scan)
- [ ] Database migrations reviewed and approved by a second engineer
- [ ] Environment variables verified against [Configuration Reference](configuration-reference.md)
- [ ] Secrets rotated if past quarterly rotation date (see [Secrets Management](secrets-management.md))
- [ ] Database backup completed and verified (see [Backup & Restore](backup-restore.md))
- [ ] Stakeholders notified of maintenance window via Slack `#deployments` channel
- [ ] ExternalSecrets sync confirmed healthy (`kubectl get externalsecrets -n hub-production`)
- [ ] PgBouncer connection pool headroom confirmed (current connections < 70% of `maxClientConn`)
- [ ] Sufficient node capacity for rolling update (at least one spare pod slot per Deployment)
- [ ] `.trivyignore` entries reviewed -- no expired CVE exceptions

## Deployment Triggers

The `deploy.yml` workflow triggers automatically on:

| Trigger | Target Environment | Notes |
|---|---|---|
| Push to `main` or `staging` branch | Staging | `MVP_MODE` set via Helm `--set` |
| Push to `release/mvp-v1` branch | Staging | Same as above |
| Push of a `v*.*.*` tag | Production | Full production pipeline |
| `workflow_dispatch` | Manual choice | Select staging or production |

For production releases, tag the commit on `main`:

```bash
git tag v1.2.3
git push origin v1.2.3
```

## Deployment Strategy

### Blue-Green via Helm Rolling Update

Meshant uses Helm `--atomic` with a 10-minute timeout. Kubernetes performs a
rolling update across all Deployments (API, worker-light, worker-heavy,
frontend, compliance, semantic, etc.). The process maintains at least
`minAvailable` pods per PodDisruptionBudget throughout the rollout:

- **API**: `pdb.minAvailable: 1`, HPA range 2-10 replicas
- **Worker Light**: `pdb.minAvailable: 1`, HPA range 2-6 replicas
- **Worker Heavy**: `pdb.minAvailable: 1`, HPA range 1-4 replicas
- **Frontend**: 2 replicas (nginx SPA, stateless)

Traffic shifts incrementally as new pods pass readiness probes before old
pods are terminated.

### Canary via Manual `workflow_dispatch`

For high-risk releases, deploy to staging first via the `staging` branch push,
then verify before tagging for production. The staging environment mirrors
production topology on a single `t3.large` node with reduced replicas (1 per
service, PDBs disabled).

To perform a controlled canary in production:

1. Deploy the new image tag to a single API pod by temporarily setting
   `api.replicaCount: 1` and `api.hpa.enabled: false` in a values override.
2. Route 5-10% of traffic using an Ingress canary annotation:
   ```yaml
   nginx.ingress.kubernetes.io/canary: "true"
   nginx.ingress.kubernetes.io/canary-weight: "5"
   ```
3. Monitor error rates and latency in Grafana for 15-30 minutes.
4. If healthy, remove the canary annotation and let HPA scale normally.
5. If unhealthy, delete the canary Ingress and roll back (see below).

## Deployment Steps

### 1. Build Artifacts

The `build` job in `deploy.yml` builds all service images and tags them with
`sha-<git-sha>`. Images are pushed to the container registry (GHCR or ECR).

```
hub/api:sha-abc1234
hub/worker:sha-abc1234
hub/frontend:sha-abc1234
hub/compliance-service:sha-abc1234
hub/backup:sha-abc1234
```

### 2. Sign and Scan

- **cosign**: Keyless OIDC signing via Sigstore with SBOM attestation.
  The `ClusterImagePolicy` resource (when `cosign.enabled: true`) enforces
  that only signed images from trusted workflow refs can be admitted.
- **Trivy**: Scans all images; the pipeline exits with failure on any
  CRITICAL-severity finding not listed in `.trivyignore`.

### 3. Run Migrations

Migrations run as part of the Helm upgrade when the API pod starts. Django's
`migrate` management command executes during container startup (before Gunicorn
binds). For destructive migrations (column drops, table renames):

- Test the migration against a snapshot of production data first.
- Ensure the migration is backwards-compatible with the previous release
  (the old code may still be serving traffic during the rolling update).
- If a migration requires downtime, coordinate a maintenance window.

### 4. Deploy via Helm

The `deploy` job runs:

```bash
helm upgrade hub helm/ \
  -f helm/values.yaml \
  --set api.image.tag=sha-${GIT_SHA} \
  --set worker.image.tag=sha-${GIT_SHA} \
  --set frontend.image.tag=sha-${GIT_SHA} \
  --atomic \
  --timeout 10m \
  --namespace hub-production
```

For staging, the workflow additionally applies `values.staging.yaml` and sets
`api.env.MVP_MODE=true`.

### 5. Smoke Tests

The `smoke` job runs `pytest tests/smoke/` against the live deployment URL.
It authenticates with `SMOKE_ADMIN_EMAIL` / `SMOKE_ADMIN_PASSWORD` and
verifies:

- `/health/` returns 200 with all dependencies healthy
- `/health/live/` returns 200 (liveness endpoint, no I/O)
- Authentication flow (login, token refresh)
- Core API endpoints return expected status codes

If smoke tests fail, the pipeline triggers an automatic rollback.

## Rollback Procedure

### Automatic Rollback (Smoke Failure)

When smoke tests fail, the workflow runs:

```bash
helm rollback hub --namespace hub-production --timeout 5m
```

### Manual Rollback

```bash
# List recent releases
helm history hub -n hub-production

# Roll back to the previous release
helm rollback hub <REVISION> -n hub-production --timeout 5m

# Verify pods are healthy
kubectl get pods -n hub-production -w
```

### Migration Rollback

If a database migration must be reverted:

```bash
# Identify the migration to revert
kubectl exec -it deploy/hub-api -n hub-production -- \
  python manage.py showmigrations <app_name>

# Revert to a specific migration
kubectl exec -it deploy/hub-api -n hub-production -- \
  python manage.py migrate <app_name> <previous_migration>
```

Always test migration rollbacks in staging first.

## Post-Deployment Verification

### Health Checks

```bash
# Deep health check (DB + Redis + microservices)
curl -s https://apimeshant-internal.example.com/health/ | jq .

# Liveness (lightweight, no I/O)
curl -s https://apimeshant-internal.example.com/health/live/ | jq .
```

### Monitoring Dashboard

Open the Grafana deployment dashboard and verify:

- **HTTP error rate** < 0.1% (5xx responses)
- **p99 latency** < 2s for API endpoints
- **Pod restart count** = 0 for all Deployments
- **RQ queue depth** trending down (no job backlog)
- **PgBouncer active connections** within pool limits
- **Memory usage** stable (no upward trend indicating leaks)

### Alerting

Verify that Prometheus alerting rules are firing correctly:

- `HubAPIHighErrorRate` -- triggers if 5xx rate > 1% for 5 minutes
- `HubReplicationLagHigh` -- triggers if pg_replication_lag > 30s
- `HubWorkerQueueBacklog` -- triggers if queue depth > 500 for 10 minutes
- `HubPodCrashLooping` -- triggers on repeated container restarts

### Post-Deploy Communication

After a successful deployment:

1. Post a summary in `#deployments` Slack channel with the release tag,
   key changes, and links to the PR(s).
2. Update the deployment log (internal wiki) with the release version,
   timestamp, and any incidents encountered.
3. Monitor for 30 minutes before closing the maintenance window.
