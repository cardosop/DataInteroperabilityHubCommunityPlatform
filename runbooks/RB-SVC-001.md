# RB-SVC-001: Service Crash / High Error Rate

**Runbook ID:** `RB-SVC-001`  
**Title:** Service Crash / High Error Rate  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers response procedures for service crashes, high error rates, and service degradation.

**In Scope:**
- Service crashes and restarts
- High 5xx error rates
- High latency
- Out of memory (OOM) errors

**Out of Scope:**
- Database issues (see `RB-DB-001`)
- Queue issues (see `RB-QUEUE-001`)

---

## Symptoms

### Alert Names

- `service_5xx_rate_high` - High 5xx error rate
- `service_latency_high` - High latency
- `service_crash_loop` - Service restarting repeatedly
- `service_oom` - Out of memory

### User-Visible Symptoms

- API endpoints returning 500 errors
- High response times
- Service unavailable
- Intermittent failures

### Log Examples

```
ERROR: Out of memory: killed process
ERROR: Service crashed: signal 9
ERROR: 500 Internal Server Error
WARN: High error rate: 10% of requests failing
```

---

## Detection & Diagnosis

### Step 1: Check Service Health

```bash
# Check pod status
kubectl get pods -l app=api-service -n production

# Check for crash loops
kubectl get pods -l app=api-service -n production | grep CrashLoopBackOff
```

### Step 2: Check Recent Deployments

```bash
# Check deployment history
kubectl rollout history deployment/api-service -n production

# Check recent deployments
kubectl get deployments api-service -n production -o yaml | grep image:
```

### Step 3: Check Logs

```bash
# Recent logs
kubectl logs deployment/api-service -n production --tail=100

# Error logs
kubectl logs deployment/api-service -n production | grep -i error

# Check for OOM
kubectl logs deployment/api-service -n production | grep -i "out of memory"
```

### Step 4: Check Metrics

**Grafana Dashboard:**
- Error rate
- Latency (p50, p95, p99)
- Memory usage
- CPU usage
- Restart count

---

## Immediate Actions

### If Recent Deployment Correlates

**1. Consider Rollback:**
```bash
# Rollback to previous version
kubectl rollout undo deployment/api-service -n production

# Verify rollback
kubectl rollout status deployment/api-service -n production
```

### If Resource Exhaustion

**1. Temporarily Scale:**
```bash
# Scale down to reduce load
kubectl scale deployment/api-service --replicas=2 -n production

# Or increase resources
kubectl set resources deployment/api-service \
  --requests=memory=2Gi \
  --limits=memory=4Gi \
  -n production
```

### For Critical Endpoints

**1. Enable Feature Flags:**
```bash
# Disable non-critical features
kubectl set env deployment/api-service \
  DISABLE_NON_CRITICAL_FEATURES=true \
  -n production
```

---

## Remediation

### Step 1: Rollback (if deployment-related)

```bash
# Rollback to previous version
kubectl rollout undo deployment/api-service -n production

# Or rollback to specific revision
kubectl rollout undo deployment/api-service --to-revision=2 -n production
```

### Step 2: Fix Configuration

**Update Configuration:**
```bash
# Update environment variables
kubectl set env deployment/api-service \
  NEW_CONFIG_VALUE=value \
  -n production

# Restart to apply
kubectl rollout restart deployment/api-service -n production
```

### Step 3: Scale Resources

**Increase Resources:**
```bash
# Increase memory/CPU
kubectl set resources deployment/api-service \
  --requests=cpu=2,memory=4Gi \
  --limits=cpu=4,memory=8Gi \
  -n production
```

**Scale Horizontally:**
```bash
# Increase replicas
kubectl scale deployment/api-service --replicas=5 -n production
```

---

## Validation

### Success Criteria

**Service is healthy when:**
- ✅ Error rate < 0.5%
- ✅ Latency p95 < 300ms
- ✅ No crash loops
- ✅ Memory usage < 80%
- ✅ All health checks passing

### Validation Steps

**1. Check Service Status:**
```bash
# Pod status
kubectl get pods -l app=api-service -n production

# Health check
curl https://api.[domain]/health/
```

**2. Monitor Metrics:**
- Error rate trending down
- Latency returning to baseline
- No new crashes

**3. Run Smoke Tests:**
```bash
make smoke-test-production
```

---

## Communication

**Internal:**
```
🚨 Service Crash Detected
Service: api-service
Status: Investigating
Action: [Rolling back / Scaling / etc.]
```

**Resolution:**
```
✅ Service Crash Resolved
Service: api-service
Status: Healthy
Duration: [X minutes]
```

---

## Post-Incident

- [ ] Document incident
- [ ] Review resource limits
- [ ] Update monitoring
- [ ] Fix root cause

---

## Related Runbooks

- `RB-DEPLOY-001`: Standard Deployment Procedure
- `RB-DB-001`: Database Outage
- `RB-QUEUE-001`: Queue Backlog

