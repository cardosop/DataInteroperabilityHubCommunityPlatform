# RB-DEPLOY-002: Rollback Procedure

**Runbook ID:** `RB-DEPLOY-002`  
**Title:** Production Rollback Procedure  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers rollback procedures for production deployments when issues are detected.

**In Scope:**
- Application rollback (code/configuration)
- Database migration rollback (when applicable)
- Service rollback verification
- Post-rollback validation

**Out of Scope:**
- Infrastructure rollback (covered separately)
- Data recovery (see `RB-DB-003`)

---

## Rollback Triggers

Rollback should be initiated immediately if:

1. **Critical Errors**: Error rate > 5% for 5 minutes
2. **Service Degradation**: P95 latency > 1s for 5 minutes
3. **Service Unavailability**: Health checks failing
4. **Data Corruption**: Database integrity issues detected
5. **Security Issues**: Security vulnerabilities discovered
6. **Business Impact**: User-reported critical issues

---

## Rollback Procedures

### Blue-Green Rollback

**Step 1: Switch Traffic Back to Blue**

```bash
# Switch service selector back to blue
kubectl patch service api-service -p '{"spec":{"selector":{"version":"blue"}}}'

# Verify traffic switched
kubectl get endpoints api-service
```

**Step 2: Verify Rollback**

```bash
# Check pod status
kubectl get pods -l version=blue

# Verify health endpoints
curl https://api.hub.example.com/health/

# Monitor metrics
# (Check Grafana dashboard)
```

**Step 3: Monitor for 30 Minutes**

- Error rate should return to baseline
- Latency should return to baseline
- All services healthy

### Rolling Deployment Rollback

**Step 1: Rollback Deployment**

```bash
# Rollback to previous revision
kubectl rollout undo deployment/api-service

# Or rollback to specific revision
kubectl rollout undo deployment/api-service --to-revision=2

# Monitor rollback status
kubectl rollout status deployment/api-service
```

**Step 2: Verify Rollback**

```bash
# Check deployment status
kubectl get deployment api-service

# Verify pods are running
kubectl get pods -l app=api-service

# Check health endpoints
curl https://api.hub.example.com/health/
```

**Step 3: Monitor for 30 Minutes**

- Error rate should return to baseline
- Latency should return to baseline
- All services healthy

### Canary Rollback

**Step 1: Remove Canary Traffic**

```bash
# Route 0% traffic to canary
kubectl patch service api-service -p '{"spec":{"traffic":{"canary":0}}}'

# Scale down canary deployment
kubectl scale deployment api-service-canary --replicas=0
```

**Step 2: Verify Rollback**

```bash
# Verify all traffic routed to stable
kubectl get endpoints api-service

# Monitor metrics
# (Check Grafana dashboard)
```

---

## Database Rollback

**⚠️ Warning**: Database rollbacks are complex and should be avoided. Always test migrations in staging first.

### Forward-Compatible Migrations

If migrations are forward-compatible, no rollback needed:

```bash
# Verify migration status
python manage.py showmigrations

# Check for data integrity
python manage.py check --database default
```

### Backward-Compatible Rollback

If migration supports rollback:

```bash
# Rollback specific migration
python manage.py migrate app_name previous_migration_name

# Verify rollback
python manage.py showmigrations
```

### Full Database Restore

If migration caused data corruption:

```bash
# Stop application services
kubectl scale deployment api-service --replicas=0

# Restore from backup
kubectl exec -it postgres-0 -- psql -U hub hub < backup-YYYYMMDD-HHMMSS.sql

# Verify restore
kubectl exec -it postgres-0 -- psql -U hub hub -c "SELECT COUNT(*) FROM table_name;"

# Restart services
kubectl scale deployment api-service --replicas=3
```

---

## Rollback Verification

### Health Checks

```bash
# Verify all health endpoints
curl https://api.hub.example.com/health/
curl https://api.hub.example.com/api/v1/health/semantic/
curl https://api.hub.example.com/api/v1/health/datacontract/
curl https://api.hub.example.com/api/v1/health/compliance/
curl https://api.hub.example.com/api/v1/health/dq/
```

### Smoke Tests

```bash
# Run smoke tests
./scripts/smoke-tests.sh --api-url https://api.hub.example.com
```

### Metrics Verification

- [ ] Error rate returned to baseline (< 0.5%)
- [ ] Latency returned to baseline (P95 < 300ms)
- [ ] All services healthy
- [ ] No crash loops
- [ ] Job processing working

---

## Post-Rollback Actions

### 1. Document Rollback

- Record rollback timestamp
- Document reason for rollback
- Note issues encountered
- Update deployment log

### 2. Investigate Root Cause

- Review logs from failed deployment
- Analyze metrics during failure
- Identify root cause
- Create follow-up ticket

### 3. Communication

**Notify Team:**
```
⚠️ Production Rollback Performed
Time: [timestamp]
Version: v1.2.3 → v1.2.2
Reason: [reason]
Status: Rolled back successfully
Next Steps: [investigation ticket]
```

### 4. Fix and Re-deploy

- Fix identified issues
- Test fixes in staging
- Re-deploy with fixes
- Monitor closely

---

## Related Runbooks

- `RB-DEPLOY-001`: Standard Deployment Procedure
- `RB-DB-002`: Database Migration Rollback
- `RB-SVC-001`: Service Crash Recovery

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

