# Production Deployment Runbook — Meshant Hub

**Version:** 1.0  
**Date:** 2026-05-15  
**Owner:** Platform Engineering  
**Review status:** Pending 2-engineer review (280.C.6.1)

## 1. Pre-Deploy Checklist

Complete every item before starting a production deployment. If any check fails, abort and escalate.

### 1.1 — Staging Validation (mandatory)

- [ ] Latest `staging` branch deploy completed successfully (green CI: `.github/workflows/deploy.yml`)
- [ ] k6 critical journeys load test passed against staging (`tests/load/critical_journeys.k6.js`)
- [ ] E2E smoke tests pass against staging (`.github/workflows/e2e-pr-smoke.yml`)
- [ ] `terraform plan` against staging shows zero unexpected drift
- [ ] Staging has been running the candidate commit for ≥1 hour with no SEV1 alerts
- [ ] Synthetic probes (login, asset_list, search, health) green for ≥30 min

### 1.2 — Database Migrations (mandatory)

- [ ] `python manage.py makemigrations --check` produces zero output (no missing migrations)
- [ ] All migrations have been run against staging and verified
- [ ] Backwards-incompatible migrations have a documented rollback plan (see §4)
- [ ] RLS policies linted: `python scripts/lint_rls_policies.py` passes

### 1.3 — Infrastructure (mandatory)

- [ ] `terraform plan` in `infrastructure/terraform/environments/prod` shows expected changes only
- [ ] No manual AWS console changes pending (drift check)
- [ ] AWS Secrets Manager: all required secrets present and non-expired
- [ ] ECR images for all services built and tagged with the deploy SHA
- [ ] Helm values files reviewed and committed

### 1.4 — Operational Readiness

- [ ] On-call engineer notified and available for the deploy window
- [ ] Grafana dashboards healthy (no data gaps)
- [ ] AlertManager silence rules reviewed (no active silences hiding known issues)
- [ ] Incident response channel (#meshant-incidents) monitored
- [ ] Rollback procedure reviewed by deployer

### 1.5 — Communications

- [ ] Maintenance window communicated to tenants (see `docs/operations/maintenance-template.md`) if downtime expected
- [ ] Stakeholder sign-off obtained (Engineering Lead or CTO per launch governance)

## 2. Deploy Steps

### 2.1 — Initiate Deploy

```bash
# 1. Merge to main (or push to release/* branch)
# 2. CI triggers .github/workflows/deploy.yml automatically
# 3. Monitor: https://github.com/cardosop/DataInteroperabilityHub/actions
```

### 2.2 — Deploy Sequence (automated by CI)

The CI pipeline executes in this order. Do NOT skip steps manually.

| Step | Action | Timeout | Rollback Trigger |
|---|---|---|---|
| 1 | `docker build` + push to ECR (all services) | 20 min | Build failure |
| 2 | `terraform plan` (prod environment) | 5 min | Unexpected resource churn |
| 3 | `terraform apply` (prod environment) | 15 min | Apply failure |
| 4 | `helm upgrade` (api, worker, frontend, services) | 10 min | Helm failure |
| 5 | `kubectl rollout status` (all deployments) | 5 min | Timeout |
| 6 | Database migrations (`python manage.py migrate`) | 5 min | Migration failure |
| 7 | Post-deploy smoke tests | 3 min | Test failure |

### 2.3 — Manual Verification (while CI runs)

```bash
# Watch pod status
kubectl get pods -n hub-production --watch

# Watch deploy events
kubectl get events -n hub-production --sort-by=.lastTimestamp | tail -20

# Verify new pods are serving traffic
kubectl logs -n hub-production -l app=api-service --tail=5
```

## 3. Post-Deploy Verification

### 3.1 — Immediate (within 5 minutes of deploy completing)

- [ ] All pods in `hub-production` namespace are Running and Ready
- [ ] `kubectl get pods -n hub-production` shows zero CrashLoopBackOff / Error / Pending
- [ ] Health endpoint responds: `curl -sf https://meshant-internal.example.com/health`
- [ ] Login flow works: `curl -X POST https://meshant-internal.example.com/api/v1/auth/login/ ...`
- [ ] Asset list returns data: `curl -H "Authorization: Bearer $TOKEN" https://meshant-internal.example.com/api/v1/assets/`
- [ ] Search returns results: `curl -H "Authorization: Bearer $TOKEN" "https://meshant-internal.example.com/api/v1/search/?q=test"`
- [ ] No critical alerts firing in Grafana / AlertManager

### 3.2 — Within 15 minutes

- [ ] Synthetic probes (login, asset_list, search, health) all green
- [ ] k6 quick smoke test passes (5-minute run vs production)
- [ ] Loki shows structured logs from all services with no ERROR spikes
- [ ] Tempo shows traces flowing end-to-end (check a login trace)
- [ ] Prometheus metrics show healthy request rates and latencies

### 3.3 — Within 1 hour

- [ ] P95 latency within baseline for all 10 critical journeys
- [ ] Error rate <1% across all API endpoints
- [ ] Database connection pool healthy (pgbouncer metrics)
- [ ] Redis connection pool healthy (all 4 instances responsive)
- [ ] No SEV1 or SEV2 alerts triggered

### 3.4 — Within 24 hours

- [ ] Daily cost anomaly check passes (AWS Cost Explorer)
- [ ] Backup verification: RDS snapshot completed successfully
- [ ] S3 bucket metrics show expected usage patterns
- [ ] Loki log volume within expected range (no log storms)

## 4. Rollback Procedure

### 4.1 — When to Roll Back

Rollback immediately if ANY of:
- Error rate exceeds 5% for >2 minutes
- P95 latency exceeds 5× baseline for >2 minutes
- Any SEV1 alert fires (service down, data loss, auth broken)
- Database migration fails
- Pods fail to become Ready within 5 minutes

### 4.2 — Rollback Steps

```bash
# 1. Revert to previous known-good Helm release
helm rollback meshant -n hub-production

# 2. If Helm rollback fails, deploy previous image tag
kubectl set image deployment/api-service \
  api-service=<ecr-registry>/api-service:<previous-sha> \
  -n hub-production

# 3. Rollback database migration (if applicable)
python manage.py migrate <app> <previous-migration-number>

# 4. Verify rollback
kubectl rollout status deployment/api-service -n hub-production
curl -sf https://meshant-internal.example.com/health

# 5. Notify incident channel
# "Production deploy rolled back to <previous-sha>. Reason: <reason>.
#  Incident: <link>. ETA for fix: <ETA>."
```

### 4.3 — Database Migration Rollback Safety

- Only migrations with `Reverse` operations (Django reversible migrations) can be rolled back
- For backwards-incompatible migrations (column drops, NOT NULL additions), the rollback is `python manage.py migrate <app> <previous-number>`
- If migration is irreversible: deploy the previous code version that's compatible with the new schema
- **NEVER** manually edit the production database during rollback

### 4.4 — Compose-path rollback (internal beta window, Phase U.6)

Until the EKS migration (ticket 210.29, owner `admin`, expiry 2026-09-30),
the beta stack runs on `docker compose -f docker-compose.staging.yml
--env-file .env.staging` — Compose has no release history, so rollback is
**revert-the-revision + re-apply**:

```bash
# 1. Record the known-good pin before any change
git rev-parse HEAD > .staging-known-good-sha
docker compose -f docker-compose.staging.yml --env-file .env.staging \
  config > .staging-known-good-config.yml

# 2. To roll back: restore the known-good revision and re-apply
git checkout "$(cat .staging-known-good-sha)" -- .
make staging-up
make staging-post-deploy   # migrations + seed + health + MinIO + email + MVP gate
```

The data volumes are named (`pgdata-staging`, `minio-data-staging`, the four
`redis-*-data-staging`) and survive `staging-down` — rollback never destroys
beta data; `staging-down-volumes` is the destructive variant and requires the
backup check from §5.2 first.

## 5. Backup & Restore (drilled)

### 5.1 — Production path (EKS / RDS)

- RDS automated snapshots (daily, retained 7 days) + `scripts/backup-postgres.sh`
  (pg_dump → S3 + SHA-256 manifest + retention sweep) — policy and restore
  drills in `docs/operations/disaster-recovery-policy.md`
  (`scripts/dr/restore_verify_rds.sh`, quarterly cadence).

### 5.2 — Compose-path staging (beta window)

`make staging-backup` / `make staging-restore-drill`
(`infrastructure/scripts/staging-compose-backup-restore.sh`):

- `backup` — pg_dump (custom format) of the staging postgres + SHA-256
  manifest + MinIO bucket mirror into `backups/staging/`, retention sweep
  (default 14 days, `RETENTION_DAYS=` override).
- `restore-drill` — restores the latest dump into a scratch database
  (`hub_staging_restore_drill`), verifies the manifest, checks row-count
  parity (tenants/users/audit/billing tables) against the live database, then
  drops the scratch DB. Exit non-zero on ANY mismatch — a backup that cannot
  be restored is not a backup.
- The live database is only ever READ; the drill never touches it.

### 5.3 — Drill evidence

| Date | Drill | Result |
|---|---|---|
| 2026-09-02 | compose staging backup (`make staging-backup`) | PASS — `hub_staging_2026-09-02T183107Z.dump` (custom format) + SHA-256 manifest + MinIO mirror into `backups/staging/` |
| 2026-09-02 | compose staging restore drill (`make staging-restore-drill`) | PASS — manifest verified; scratch DB restored; row-count parity 5/5 (tenants 4=4, users 27=27, audit_events 27=27, tenant_plans 8=8, api_keys 0=0); scratch dropped |
| 2026-09-02 | compose staging rollback rehearsal | Procedure exercised: known-good pin recorded (`.staging-known-good-sha` + `.staging-known-good-config.yml`, gitignored); the re-apply + verify leg ran repeatedly during the bring-up (every `make staging-up` + `make staging-post-deploy` cycle, final 22/22 checks green). A full prior-revision revert will be rehearsed at U.8 with the first real rollback candidate. |

## 6. Emergency Contacts

### 5.1 — Escalation Path

| Priority | Role | Contact |
|---|---|---|
| P1 | On-call Engineer | PagerDuty: meshant-oncall |
| P2 | Platform Lead | Slack: @platform-lead |
| P3 | CTO | Email: cto@meshant.com |

### 5.2 — External Dependencies

| Service | Status Page | Support |
|---|---|---|
| AWS (us-east-1) | https://health.aws.amazon.com | AWS Support (Business plan) |
| Stripe | https://stripe.statuspage.io | dashboard.stripe.com/support |
| Let's Encrypt | https://letsencrypt.status.io | community.letsencrypt.org |
| GitHub Actions | https://www.githubstatus.com | GitHub Support |

### 5.3 — Internal Communication Channels

| Channel | Purpose |
|---|---|
| `#meshant-incidents` | Active incident coordination (SEV1/SEV2) |
| `#meshant-eng` | Engineering team coordination |
| `#meshant-deploy` | Automated deploy notifications (CI bot) |

## 7. Deploy Freeze Policy

- **Standard freeze:** No deploys Friday 17:00 UTC – Monday 08:00 UTC
- **Holiday freeze:** No deploys during company-wide holidays (calendar published in `#meshant-eng`)
- **Exception process:** Engineering Lead + CTO approval required; documented in incident channel
- **Emergency hotfix:** On-call engineer may deploy without freeze waiver for SEV1 fixes; post-deploy review required within 24h

## 8. Runbook Maintenance

- **Owner:** Platform Engineering
- **Review cadence:** Quarterly (next: 2026-08-15)
- **Update triggers:** After every SEV1 incident, after major infrastructure change, after new service addition
