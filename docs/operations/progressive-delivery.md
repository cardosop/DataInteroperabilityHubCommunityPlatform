# Progressive Delivery — Meshant Platform

**Last updated:** 2026-05-15

## B.5.1 — Automated Canary Deployments

**Status:** ⏭️ Infrastructure exists, Argo Rollouts needed.

### Existing Infrastructure
- `helm/values.staging.yaml:399`: canary/HA config (`replicaCount: 2`, `maxUnavailable=0`)
- `k6-load-test-gate.yml`: performance baseline comparison, 14 canary/rollback refs
- `helm-rollback.yml`: automated rollback workflow (118 lines)

### Canary Traffic Shift Stages
```
Stage 1: 5% traffic → new version  (2 min validation)
  ├── Metrics: error rate, p95 latency, CPU
  ├── Pass → Stage 2
  └── Fail → auto-rollback (B.5.2)

Stage 2: 25% traffic → new version (5 min validation)
  ├── Metrics: error rate, p95 latency, CPU
  ├── Pass → Stage 3
  └── Fail → auto-rollback (B.5.2)

Stage 3: 100% traffic → new version (10 min validation)
  ├── Metrics: error rate, p95 latency, CPU
  ├── Pass → promote (stable)
  └── Fail → auto-rollback (B.5.2)
```

### Argo Rollouts Configuration
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
spec:
  replicas: 3
  strategy:
    canary:
      steps:
      - setWeight: 5
      - pause: {duration: 2m}
      - setWeight: 25
      - pause: {duration: 5m}
      - setWeight: 100
      - pause: {duration: 10m}
      analysis:
        templates:
        - templateName: canary-analysis
        args:
        - name: service-name
          value: hub-api
```

## B.5.2 — Automated Rollback

**Status:** ✅ WORKFLOW EXISTS (verified 2026-05-15).

### Rollback Triggers
| Metric | Baseline | Threshold | Action |
|---|---|---|---|
| Error rate (5xx) | Current stable | >2× baseline | Immediate rollback |
| p95 latency | Current stable | >1.5× baseline | Immediate rollback |
| CPU utilization | Current stable | >90% sustained | Rollback after 2 min |
| Health check | 200 OK | Non-200 | Immediate rollback |

### Rollback Procedure
```bash
# 1. Detect canary failure (Prometheus alert or Argo Rollouts analysis)
# 2. Helm rollback to previous revision
helm rollback hub-staging $(helm history hub-staging --max 1 --output json | jq '.[0].revision')

# 3. Verify rollback
kubectl rollout status deployment/hub-api -n hub-staging

# 4. Postmortem ticket created automatically
```

**CI workflow:** `.github/workflows/helm-rollback.yml` (118 lines) — automated rollback triggered by Prometheus alert webhook.

## B.5.3 — Feature Flag-Driven Deployments

**Status:** ✅ INFRASTRUCTURE EXISTS (verified 2026-05-15).

### Flag Lifecycle
```
DRAFT   → Code deployed dark, no tenant access
CANARY  → Opt-in for friendly tenants (1-3 tenants)
GA      → Enabled for all tenants (default True or explicit opt-in)
DEPRECATED → Marked for removal, retire_by date set
RETIRED → Code removed, flag deleted from registry
```

### Current Distribution
| Stage | Count | Meaning |
|---|---|---|
| DRAFT | 4 | Deployed dark |
| CANARY | 13 | Available for opt-in |
| GA | 10 | Generally available |
| DEPRECATED | 0 | — |

### Deploy-Dark → Enable Flow
```bash
# 1. Deploy feature behind DRAFT flag (code deployed, no access)
git push staging  # deploys with flag in DRAFT stage

# 2. Promote to CANARY (enable for friendly tenants)
datahub admin feature-flags update --tenant-id <friendly> --flag new_feature_enabled=true

# 3. Monitor Canary for 7 days
# Metrics: adoption rate, error rate, latency for canary tenants

# 4. Promote to GA (after validation)
# Update feature_flag_registry.py: stage="CANARY" → stage="GA"

# 5. Retire after 2 release cycles (if superseded)
```

### Deployment Validation per Stage
| Stage | Validation Gate | Duration |
|---|---|---|
| DRAFT→CANARY | CI passes + manual QA | 1 day |
| CANARY→GA | 3 friendly tenants, 7 days stable, zero SEV1 | 7 days |
| GA→DEPRECATED | announce 1 release prior, 30-day notice | 30 days |
