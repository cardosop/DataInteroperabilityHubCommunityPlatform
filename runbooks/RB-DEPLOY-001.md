# RB-DEPLOY-001: Standard Deployment Procedure

**Runbook ID:** `RB-DEPLOY-001`
**Title:** Standard Deployment Procedure
**Last Updated:** 2025-01-15
**Version:** 1.0

---

## Scope

This runbook covers routine application releases in **staging** and **production** environments for the Interoperable Data Hub MVP.

**In Scope:**
- Application code deployments
- Database migrations (forward-only)
- Configuration updates
- Service restarts and rolling updates

**Out of Scope:**
- Infrastructure provisioning (covered in separate runbooks)
- Emergency hotfixes (see `RB-DEPLOY-002`)
- Rollback-only procedures (see `RB-DEPLOY-003`)

---

## Audience & Roles

**Primary Users:**
- DevOps engineers
- SRE team members
- Release managers

**Required Permissions:**
- Access to CI/CD pipeline (GitHub Actions)
- Kubernetes/container orchestration access (for production)
- Database migration execution permissions
- Secrets manager access (for configuration updates)

---

## Prerequisites

**Tools Required:**
- `kubectl` (for Kubernetes deployments)
- `docker` / `docker-compose` (for local/staging)
- `psql` (for database operations)
- Access to CI/CD pipeline dashboard
- Access to monitoring dashboards (Grafana, Prometheus)

**Access Required:**
- GitHub repository (read/write)
- Kubernetes cluster access
- Database admin access
- Secrets manager access (AWS Secrets Manager, HashiCorp Vault, etc.)

**Links:**
- CI/CD Pipeline: `https://github.com/[org]/DataInteroperabilityHub/actions`
- Monitoring Dashboard: `https://grafana.[domain]/d/hub-overview`
- Deployment Logs: `https://github.com/[org]/DataInteroperabilityHub/actions/workflows/deploy.yml`

---

## Pre-Deployment Checks

### 1. Code Quality Checks

```bash
# All tests must pass
make test

# Linting must pass
make lint

# Type checking must pass
make type-check
```

**Required:**
- ✅ All unit tests passing
- ✅ All integration tests passing
- ✅ Migration tests passing (if applicable)
- ✅ No linting errors
- ✅ No type checking errors

### 2. Change Approval

- ✅ Change ticket approved (if required by process)
- ✅ Code review completed and approved
- ✅ All required approvals obtained

### 3. Environment Status

- ✅ No active SEV-1 or SEV-2 incidents
- ✅ All services healthy in target environment
- ✅ Database connection pool not exhausted
- ✅ Queue backlog within normal limits

### 4. Backup Verification

- ✅ Database backup completed within last 24 hours
- ✅ Backup integrity verified
- ✅ Rollback plan documented

---

## Deployment Steps

### Stage 1: Deploy to Staging

**1.1 Trigger Staging Deployment**

```bash
# Via GitHub Actions
# Navigate to: Actions > Deploy to Staging > Run workflow

# Or via CLI (if configured)
gh workflow run deploy-staging.yml
```

**1.2 Monitor Deployment**

Watch for:
- Deployment status in CI/CD dashboard
- Pod/service health in Kubernetes
- Error rates in monitoring dashboard

**1.3 Run Smoke Tests**

```bash
# Run smoke test suite
make smoke-test-staging

# Or manually verify:
curl https://staging.[domain]/health/
curl https://staging.[domain]/api/v1/tenants/
```

**Expected Results:**
- Health endpoint returns `200 OK`
- API endpoints respond correctly
- No error spikes in metrics

**1.4 Validate Database Migrations**

```bash
# Check migration status
python manage.py showmigrations

# Verify no pending migrations
python manage.py migrate --check
```

**If smoke tests fail:**
- Stop deployment
- Investigate failures
- Fix issues and restart from Stage 1

---

### Stage 2: Production Canary Deployment

**2.1 Deploy to Canary Environment**

```bash
# Deploy to canary (10% of traffic)
# Via Kubernetes:
kubectl set image deployment/api-service api-service=hub-api:${VERSION} -n production
kubectl scale deployment/api-service-canary --replicas=1 -n production
```

**2.2 Monitor Canary**

**Watch Metrics (First 10 minutes):**
- Error rate: Should remain < 1%
- Latency p95: Should remain < 500ms
- Database connection pool: Should remain < 80%
- Queue depth: Should remain stable

**Watch Logs:**
```bash
# Monitor canary pod logs
kubectl logs -f deployment/api-service-canary -n production

# Check for errors
kubectl logs deployment/api-service-canary -n production | grep -i error
```

**2.3 Validate Canary**

**Run Smoke Tests:**
```bash
make smoke-test-production-canary
```

**Check Critical Paths:**
- User authentication
- Asset creation
- Contract validation
- File upload

**If canary shows issues:**
- Immediately rollback canary
- Investigate root cause
- Fix issues before proceeding

---

### Stage 3: Full Production Rollout

**3.1 Deploy to All Production Replicas**

```bash
# Rolling update (Kubernetes handles this automatically)
kubectl set image deployment/api-service api-service=hub-api:${VERSION} -n production

# Monitor rollout status
kubectl rollout status deployment/api-service -n production
```

**3.2 Monitor Full Rollout**

**Watch Metrics (First 30 minutes):**
- Error rate: Should remain < 0.5%
- Latency p95: Should remain < 300ms
- All services healthy
- No crash loops

**Watch Dashboards:**
- Grafana: `https://grafana.[domain]/d/hub-overview`
- Prometheus: `https://prometheus.[domain]/graph`

**3.3 Validate Deployment**

**Run Full Test Suite:**
```bash
make test-production-smoke
```

**Verify Critical Operations:**
- ✅ User login/logout
- ✅ Asset CRUD operations
- ✅ Contract creation and validation
- ✅ File upload/download
- ✅ Job processing
- ✅ DQ/compliance runs

**Verify Compliance and DQ Endpoints:**
```bash
# Test compliance endpoints
curl -X GET https://api.[domain]/api/v1/compliance/runs/ \
  -H "Authorization: Bearer <token>"

curl -X GET https://api.[domain]/api/v1/compliance/runs/{id}/ \
  -H "Authorization: Bearer <token>"

# Test DQ endpoints
curl -X GET https://api.[domain]/api/v1/dq/runs/ \
  -H "Authorization: Bearer <token>"

curl -X GET https://api.[domain]/api/v1/dq/runs/{id}/ \
  -H "Authorization: Bearer <token>"

# Verify old patterns return 404 (deprecated - DO NOT USE)
# These endpoints are deprecated and should return 404:
# curl -X GET https://api.[domain]/api/v1/compliance/compliance-runs/  # DEPRECATED - returns 404
# curl -X GET https://api.[domain]/api/v1/dq/dq-runs/  # DEPRECATED - returns 404
```

**Expected Results:**
- ✅ Compliance endpoints (`/api/v1/compliance/runs/`) return 200 OK or 401 Unauthorized
- ✅ DQ endpoints (`/api/v1/dq/runs/`) return 200 OK or 401 Unauthorized
- ✅ Old patterns (`/compliance-runs/`, `/dq-runs/`) return 404 Not Found

---

## Database Migrations

### Forward-Only Migrations

**Procedure:**
1. Migrations are applied automatically during deployment
2. Django migrations run via `python manage.py migrate`
3. Migrations are **forward-only** (no automatic rollback)

**Pre-Migration Checks:**
```bash
# Check pending migrations
python manage.py showmigrations --plan

# Dry run (check what will be executed)
python manage.py migrate --plan
```

**Migration Execution:**
```bash
# Migrations run automatically in deployment pipeline
# Or manually:
python manage.py migrate
```

**Post-Migration Validation:**
```bash
# Verify schema
python manage.py dbshell
\dt  # List tables
\d+ table_name  # Describe table

# Run data integrity checks
python manage.py check --database default
```

### Migration Rollback

**If migration fails:**
- See `RB-DB-002: Database Migration Rollback`
- Do NOT attempt automatic rollback
- Assess impact before proceeding

---

## Health Checks

### During Deployment

**Monitor These Dashboards:**
1. **Grafana Overview Dashboard**
   - HTTP request rate
   - Error rate
   - Latency (p50, p95, p99)
   - Job completion rate

2. **Prometheus Metrics**
   - `http_requests_total`
   - `http_errors_total`
   - `http_request_duration_seconds`
   - `jobs_failed_total`

3. **Application Logs**
   - Error logs
   - Warning logs
   - Database connection errors

### Error Thresholds

**Rollback Triggers:**
- Error rate > 5% for 5 minutes
- Latency p95 > 2 seconds for 5 minutes
- Database connection pool > 90% for 5 minutes
- Queue backlog > 500 jobs for 10 minutes
- Service crash loop (3+ restarts in 10 minutes)

---

## Rollback Procedure

### Automatic Rollback

**Kubernetes Rollout Rollback:**
```bash
# Rollback to previous version
kubectl rollout undo deployment/api-service -n production

# Check rollback status
kubectl rollout status deployment/api-service -n production
```

### Manual Rollback

**1. Identify Previous Version:**
```bash
# Get deployment history
kubectl rollout history deployment/api-service -n production

# View specific revision
kubectl rollout history deployment/api-service --revision=2 -n production
```

**2. Rollback to Specific Revision:**
```bash
# Rollback to revision N
kubectl rollout undo deployment/api-service --to-revision=2 -n production
```

**3. Verify Rollback:**
```bash
# Check deployment status
kubectl get deployment api-service -n production

# Verify pods are running
kubectl get pods -l app=api-service -n production

# Check metrics
# Error rate should return to baseline
# Latency should return to baseline
```

**4. Database Rollback (if needed):**
- See `RB-DB-002: Database Migration Rollback`
- **Warning:** Database rollback may cause data loss
- Only proceed if migration was the cause of issues

---

## Post-Deployment

### 1. Validation

**Run Post-Deployment Checks:**
```bash
# Health check
curl https://api.[domain]/health/

# API root
curl https://api.[domain]/api/v1/

# Verify version
curl https://api.[domain]/api/v1/ | jq .version
```

**Monitor for 1 Hour:**
- Error rates
- Latency metrics
- Job processing
- Database connections

### 2. Logs Review

**Check Deployment Logs:**
```bash
# Application logs
kubectl logs deployment/api-service -n production --tail=100

# Look for:
# - Startup errors
# - Configuration issues
# - Database connection errors
# - Service initialization failures
```

### 3. Metrics Review

**Verify Metrics:**
- All services reporting metrics
- No metric gaps
- Metrics within expected ranges

### 4. Documentation

**Update Deployment Log:**
- Deployment timestamp
- Version deployed
- Migration status
- Issues encountered
- Rollback performed (if any)

---

## Communication

### Internal Notifications

**Slack/Teams Channel:**
```
🚀 Deployment Started
Environment: Production
Version: v1.2.3
Deployed by: @username
Status: In Progress
```

**On Completion:**
```
✅ Deployment Completed
Environment: Production
Version: v1.2.3
Status: Healthy
Duration: 15 minutes
```

**On Rollback:**
```
⚠️ Deployment Rolled Back
Environment: Production
Version: v1.2.3 → v1.2.2
Reason: High error rate detected
Status: Rolled back successfully
```

### Customer-Facing (if applicable)

**Status Page Update:**
- "Deployment in progress" (during deployment)
- "Deployment completed successfully" (on success)
- "Deployment rolled back" (on rollback)

---

## Validation & Recovery

### Success Criteria

**Deployment is successful when:**
- ✅ All services healthy
- ✅ Error rate < 0.5%
- ✅ Latency p95 < 300ms
- ✅ All smoke tests passing
- ✅ No crash loops
- ✅ Database migrations applied successfully

### Recovery Steps

**If deployment fails:**
1. Execute rollback procedure (see above)
2. Verify rollback success
3. Investigate root cause
4. Create follow-up ticket
5. Document incident

---

## Post-Incident Actions

### After Successful Deployment

- ✅ Update deployment log
- ✅ Archive deployment artifacts
- ✅ Update version documentation

### After Failed Deployment

- ✅ Document failure in incident log
- ✅ Create postmortem ticket
- ✅ Update runbook if gaps found
- ✅ Fix issues before next deployment

---

## Related Runbooks

- `RB-DEPLOY-002`: Hotfix Procedure
- `RB-DEPLOY-003`: Rollback-Only Procedure
- `RB-DB-002`: Database Migration Rollback
- `RB-SVC-001`: Service Crash Recovery

---

## Appendix

### Deployment Checklist

```markdown
- [ ] Pre-deployment checks completed
- [ ] Staging deployment successful
- [ ] Smoke tests passing in staging
- [ ] Canary deployment successful
- [ ] Canary monitoring passed (10 minutes)
- [ ] Full production rollout initiated
- [ ] Production monitoring passed (30 minutes)
- [ ] Post-deployment validation completed
- [ ] Documentation updated
- [ ] Team notified
```

### Common Issues

**Issue: Migration fails**
- **Action:** Stop deployment, see `RB-DB-002`

**Issue: High error rate**
- **Action:** Rollback immediately, investigate

**Issue: Service won't start**
- **Action:** Check logs, verify configuration, rollback if needed

**Issue: Database connection errors**
- **Action:** Check connection pool, verify credentials, see `RB-DB-001`

