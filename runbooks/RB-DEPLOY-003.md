# RB-DEPLOY-003: Troubleshooting Runbook

**Runbook ID:** `RB-DEPLOY-003`  
**Title:** Deployment Troubleshooting Guide  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook provides troubleshooting procedures for common deployment issues.

**In Scope:**
- Service startup failures
- Database connection issues
- Configuration problems
- Performance degradation
- Health check failures

**Out of Scope:**
- Application bugs (see development team)
- Infrastructure failures (see infrastructure team)

---

## Common Issues and Solutions

### Issue: Services Not Starting

**Symptoms:**
- Pods in CrashLoopBackOff state
- Services not responding to health checks
- High restart count

**Diagnosis:**

```bash
# Check pod status
kubectl get pods

# Check pod logs
kubectl logs <pod-name>

# Check pod events
kubectl describe pod <pod-name>

# Check resource limits
kubectl top pods
```

**Common Causes:**

1. **Configuration Errors**
   - Missing environment variables
   - Invalid configuration values
   - Secrets not mounted

2. **Resource Constraints**
   - Insufficient CPU/memory
   - Disk space full
   - Resource quotas exceeded

3. **Dependency Issues**
   - Database not accessible
   - Redis not accessible
   - External services unavailable

**Solutions:**

```bash
# Check configuration
kubectl get configmap api-service-config -o yaml

# Check secrets
kubectl get secret api-service-secrets -o yaml

# Check resource usage
kubectl top pods
kubectl top nodes

# Check dependencies
kubectl get endpoints
```

### Issue: Database Connection Failures

**Symptoms:**
- Database connection errors in logs
- High connection pool usage
- Timeout errors

**Diagnosis:**

```bash
# Test database connection
kubectl exec -it api-service-0 -- python manage.py dbshell

# Check database status
kubectl get pods -l app=postgres

# Check connection pool metrics
# (View in Grafana dashboard)
```

**Common Causes:**

1. **Connection Pool Exhausted**
   - Too many connections
   - Connections not being released
   - Pool size too small

2. **Database Unavailable**
   - Database pod down
   - Network issues
   - Database overloaded

3. **Authentication Issues**
   - Invalid credentials
   - Secrets not updated
   - Permission issues

**Solutions:**

```bash
# Check database connections
kubectl exec -it postgres-0 -- psql -U hub -c "SELECT count(*) FROM pg_stat_activity;"

# Restart database connection pool
kubectl rollout restart deployment/api-service

# Verify database credentials
kubectl get secret postgres-credentials -o yaml
```

### Issue: High Error Rates

**Symptoms:**
- Error rate > 1%
- 5xx HTTP errors
- Service degradation

**Diagnosis:**

```bash
# Check error logs
kubectl logs -f deployment/api-service | grep ERROR

# Check error metrics
# (View in Grafana dashboard)

# Check service dependencies
kubectl get endpoints
```

**Common Causes:**

1. **Service Dependencies Down**
   - Microservices unavailable
   - External APIs down
   - Database issues

2. **Configuration Issues**
   - Invalid service URLs
   - Missing configuration
   - Incorrect settings

3. **Resource Constraints**
   - CPU throttling
   - Memory pressure
   - Network congestion

**Solutions:**

```bash
# Check service health
curl https://api.hub.example.com/api/v1/health/semantic/
curl https://api.hub.example.com/api/v1/health/datacontract/
curl https://api.hub.example.com/api/v1/health/compliance/
curl https://api.hub.example.com/api/v1/health/dq/

# Check resource usage
kubectl top pods

# Scale up if needed
kubectl scale deployment/api-service --replicas=5
```

### Issue: Performance Degradation

**Symptoms:**
- High latency (P95 > 500ms)
- Slow response times
- Timeout errors

**Diagnosis:**

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# Check slow queries
# (View database performance dashboard)

# Check job queue depth
# (View worker metrics)
```

**Common Causes:**

1. **Resource Constraints**
   - CPU throttling
   - Memory pressure
   - Disk I/O bottlenecks

2. **Database Performance**
   - Slow queries
   - Missing indexes
   - Connection pool issues

3. **Job Queue Backlog**
   - Too many pending jobs
   - Worker capacity insufficient
   - Job processing slow

**Solutions:**

```bash
# Scale up services
kubectl scale deployment/api-service --replicas=5
kubectl scale deployment/worker-service --replicas=3

# Check database performance
kubectl exec -it postgres-0 -- psql -U hub -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Clear job queue if needed
# (Use admin interface or CLI)
```

### Issue: Health Check Failures

**Symptoms:**
- Health endpoints returning errors
- Pods marked as unhealthy
- Services not responding

**Diagnosis:**

```bash
# Check health endpoint directly
curl -v https://api.hub.example.com/health/

# Check pod logs
kubectl logs <pod-name>

# Check liveness/readiness probes
kubectl describe pod <pod-name> | grep -A 5 "Liveness\|Readiness"
```

**Common Causes:**

1. **Application Errors**
   - Startup failures
   - Configuration errors
   - Dependency issues

2. **Probe Configuration**
   - Incorrect probe path
   - Timeout too short
   - Failure threshold too low

3. **Resource Issues**
   - CPU throttling
   - Memory pressure
   - Network issues

**Solutions:**

```bash
# Check application logs
kubectl logs <pod-name> --tail=100

# Verify probe configuration
kubectl get deployment api-service -o yaml | grep -A 10 "livenessProbe\|readinessProbe"

# Restart pod if needed
kubectl delete pod <pod-name>
```

---

## Debugging Commands

### General Debugging

```bash
# Access service shell
kubectl exec -it deployment/api-service -- bash

# Check environment variables
kubectl exec deployment/api-service -- env

# View service configuration
kubectl get configmap api-service-config -o yaml

# View secrets (base64 encoded)
kubectl get secret api-service-secrets -o yaml
```

### Database Debugging

```bash
# Access database shell
kubectl exec -it postgres-0 -- psql -U hub hub

# Check connection count
SELECT count(*) FROM pg_stat_activity;

# Check slow queries
SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;

# Check database size
SELECT pg_size_pretty(pg_database_size('hub'));
```

### Log Analysis

```bash
# View recent logs
kubectl logs deployment/api-service --tail=100

# Follow logs
kubectl logs -f deployment/api-service

# Search logs for errors
kubectl logs deployment/api-service | grep -i error

# Export logs
kubectl logs deployment/api-service > api-service.log
```

---

## Escalation

If issues cannot be resolved using this runbook:

1. **Escalate to SRE Team**
   - Provide error logs
   - Include metrics screenshots
   - Document troubleshooting steps taken

2. **Create Incident Ticket**
   - Document symptoms
   - Include relevant logs
   - Note impact

3. **Consider Rollback**
   - If issue is deployment-related
   - Follow `RB-DEPLOY-002` rollback procedure

---

## Related Runbooks

- `RB-DEPLOY-001`: Standard Deployment Procedure
- `RB-DEPLOY-002`: Rollback Procedure
- `RB-SVC-001`: Service Crash Recovery
- `RB-DB-001`: Database Troubleshooting

---

**Last Updated**: 2025-01-15  
**Version**: 1.0.0

