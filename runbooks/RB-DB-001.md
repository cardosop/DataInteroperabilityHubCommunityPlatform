# RB-DB-001: Database Outage / Degradation

**Runbook ID:** `RB-DB-001`  
**Title:** Database Outage / Degradation  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers response procedures for database outages, connection pool exhaustion, and performance degradation.

**In Scope:**
- PostgreSQL database outages
- Connection pool exhaustion
- High query latency
- Database node/replica failures

**Out of Scope:**
- Database migration issues (see `RB-DB-002`)
- Data corruption (see `RB-DR-001`)
- Backup/restore procedures (see `RB-DB-003`)

---

## Audience & Roles

**Primary Users:**
- On-call SRE engineers
- Database administrators
- DevOps engineers

**Required Permissions:**
- Database admin access (read/write)
- Cloud console access (for managed databases)
- Kubernetes access (for service scaling)
- Monitoring dashboard access

---

## Prerequisites

**Tools Required:**
- `psql` (PostgreSQL client)
- `kubectl` (for service management)
- Cloud provider CLI (AWS, GCP, Azure)
- Access to monitoring dashboards

**Access Required:**
- Database superuser or admin access
- Cloud provider console access
- Kubernetes cluster access

**Links:**
- Database Dashboard: `https://grafana.[domain]/d/database-overview`
- Monitoring: `https://prometheus.[domain]/graph`
- Cloud Console: `https://[cloud-provider].com/console`

---

## Symptoms

### Alert Names

- `db_availability_critical` - Database is unreachable
- `db_connection_pool_exhausted` - Connection pool at capacity
- `db_query_latency_high` - Query latency exceeds threshold

### User-Visible Symptoms

- API endpoints returning `500 Internal Server Error`
- High latency on database-backed endpoints
- Timeout errors
- "Database connection failed" messages

### Log Examples

**Connection Errors:**
```
ERROR: connection refused
ERROR: too many connections
ERROR: connection timeout
ERROR: database "hub" does not exist
```

**Query Timeout:**
```
ERROR: canceling statement due to statement timeout
ERROR: query timeout after 30 seconds
```

---

## Impact

**User-Visible Impact:**
- All API endpoints may be affected
- User authentication may fail
- Data operations (CRUD) may fail
- Background jobs may fail

**Severity Guidance:**
- **SEV-1 (Critical):** Full database outage, all services down
- **SEV-2 (High):** Connection pool exhausted, degraded performance
- **SEV-3 (Medium):** High latency, some operations slow

---

## Detection & Diagnosis

### Step 1: Check Database Health Dashboard

**Metrics to Check:**
- Database CPU usage
- Active connections
- Connection pool usage
- Query latency (p50, p95, p99)
- Storage I/O
- Replication lag (if applicable)

**Grafana Dashboard:**
```
https://grafana.[domain]/d/database-overview
```

### Step 2: Check Cloud Provider Status

**For Managed Databases:**
- AWS RDS: Check RDS console for instance status
- GCP Cloud SQL: Check Cloud SQL console
- Azure Database: Check Azure portal

**Check for:**
- Instance status (available, degraded, failed)
- Maintenance windows
- Storage capacity
- Network connectivity

### Step 3: Test Database Connectivity

```bash
# Test connection from application pod
kubectl exec -it deployment/api-service -n production -- \
  python manage.py dbshell

# Or directly with psql
psql -h <db-host> -U <db-user> -d hub -c "SELECT version();"
```

**Expected Results:**
- Connection succeeds
- Query returns results
- Response time < 100ms

### Step 4: Check Connection Pool Status

```sql
-- Check active connections
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';

-- Check connection pool usage
SELECT 
    max_conn,
    used_conn,
    max_conn - used_conn as available_conn
FROM (
    SELECT 
        (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_conn,
        count(*) as used_conn
    FROM pg_stat_activity
) as pool_status;
```

### Step 5: Distinguish Issue Type

**Full Outage:**
- Database instance unreachable
- All connections fail
- Cloud provider shows instance as "failed" or "unavailable"

**Connection Pool Exhausted:**
- Database is reachable
- Connection count at or near `max_connections`
- New connections are rejected

**High Latency:**
- Database is reachable
- Connections available
- Query execution time > 1 second
- CPU or I/O at high levels

**Node/Replica Failure:**
- Primary database healthy
- Read replica(s) failed
- Read operations may be affected

---

## Immediate Actions ("First 10 Minutes")

### If Database is Fully Down

**1. Page Database Team / On-Call**
- Immediately escalate to database administrators
- Provide alert details and symptoms

**2. Put System into Read-Only Mode (if supported)**
```bash
# Scale down write services
kubectl scale deployment/api-service --replicas=0 -n production

# Enable read-only mode (if configured)
kubectl set env deployment/api-service READ_ONLY_MODE=true -n production
```

**3. Notify Stakeholders**
- Send incident notification
- Update status page
- Set up incident room

### If Connection Pool Exhausted

**1. Temporarily Scale Down Services**
```bash
# Reduce API service replicas
kubectl scale deployment/api-service --replicas=2 -n production

# Reduce worker replicas
kubectl scale deployment/worker-service --replicas=1 -n production
```

**2. Identify Noisy Tenants/Endpoints**
```sql
-- Find long-running queries
SELECT 
    pid,
    usename,
    application_name,
    state,
    query_start,
    now() - query_start as duration,
    query
FROM pg_stat_activity
WHERE datname = 'hub'
  AND state != 'idle'
ORDER BY duration DESC
LIMIT 10;
```

**3. Kill Long-Running Queries (if safe)**
```sql
-- Terminate specific query
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE pid = <pid_from_above>;
```

### If High Latency

**1. Check for Lock Contention**
```sql
-- Check for blocking queries
SELECT 
    blocked_locks.pid AS blocked_pid,
    blocking_locks.pid AS blocking_pid,
    blocked_activity.query AS blocked_query,
    blocking_activity.query AS blocking_query
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks 
    ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**2. Check for Vacuum/Analyze Operations**
```sql
-- Check for autovacuum processes
SELECT 
    pid,
    datname,
    usename,
    application_name,
    state,
    query
FROM pg_stat_activity
WHERE query LIKE '%VACUUM%' OR query LIKE '%ANALYZE%';
```

---

## Remediation Procedures

### Full Outage Remediation

**1. Restart Database Instance**

**For Managed Databases (AWS RDS, GCP Cloud SQL):**
```bash
# AWS RDS
aws rds reboot-db-instance --db-instance-identifier hub-db

# GCP Cloud SQL
gcloud sql instances restart hub-db-instance
```

**For Self-Managed:**
```bash
# Restart PostgreSQL service
systemctl restart postgresql

# Or via Docker
docker restart postgres
```

**2. Fail Over to Replica (if available)**
```bash
# Promote read replica to primary
# (Procedure depends on cloud provider)

# Update application connection strings
kubectl set env deployment/api-service \
  DATABASE_HOST=<new-primary-host> \
  -n production
```

**3. Verify Recovery**
```bash
# Test connectivity
psql -h <db-host> -U <db-user> -d hub -c "SELECT 1;"

# Check service health
curl https://api.[domain]/health/
```

### Connection Pool Exhausted Remediation

**1. Increase Connection Pool Size**

**Update Application Configuration:**
```python
# In Django settings
DATABASES = {
    'default': {
        'CONN_MAX_AGE': 600,  # Reduce connection lifetime
        'OPTIONS': {
            'connect_timeout': 10,
        }
    }
}
```

**Or Increase Database max_connections:**
```sql
-- Temporary increase (requires restart)
ALTER SYSTEM SET max_connections = 200;

-- Reload configuration
SELECT pg_reload_conf();
```

**2. Optimize Connection Usage**
- Enable connection pooling (PgBouncer, PgPool)
- Reduce connection timeout
- Implement connection retry logic

**3. Scale Services Back Up**
```bash
# Gradually scale services back up
kubectl scale deployment/api-service --replicas=3 -n production
```

### High Latency Remediation

**1. Identify Slow Queries**
```sql
-- Enable query logging
ALTER SYSTEM SET log_min_duration_statement = 1000;  -- Log queries > 1s
SELECT pg_reload_conf();

-- Check slow query log
tail -f /var/log/postgresql/postgresql.log
```

**2. Optimize Queries**
- Add missing indexes
- Update table statistics: `ANALYZE table_name;`
- Rewrite inefficient queries

**3. Scale Database Resources**
- Increase CPU/memory allocation
- Upgrade instance type
- Add read replicas for read-heavy workloads

---

## Alternative / Degraded Modes

### Read-Only Mode

**Enable Read-Only Mode:**
```bash
# Set environment variable
kubectl set env deployment/api-service READ_ONLY_MODE=true -n production

# Restart services
kubectl rollout restart deployment/api-service -n production
```

**What Works:**
- Read operations (GET requests)
- Query endpoints
- Dashboard views

**What Doesn't Work:**
- Write operations (POST, PUT, DELETE)
- Job processing
- File uploads

### Maintenance Mode

**Enable Maintenance Mode:**
```bash
# Set maintenance mode
kubectl set env deployment/api-service MAINTENANCE_MODE=true -n production

# Update status page
# "System is in maintenance mode. Some features may be unavailable."
```

---

## Validation & Recovery

### Success Criteria

**Database is healthy when:**
- ✅ Connection success rate > 99%
- ✅ Query latency p95 < 100ms
- ✅ Connection pool usage < 80%
- ✅ No blocking queries
- ✅ All services can connect

### Validation Steps

**1. Check Database Metrics**
```bash
# Connection count
psql -h <db-host> -U <db-user> -d hub -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';"

# Query latency
# Check Grafana dashboard for query latency trends
```

**2. Run Smoke Tests**
```bash
# Health check
curl https://api.[domain]/health/

# API endpoints
curl https://api.[domain]/api/v1/tenants/
curl https://api.[domain]/api/v1/assets/
```

**3. Monitor for 30 Minutes**
- Watch error rates
- Watch latency metrics
- Watch connection pool usage
- Check application logs

---

## Communication

### Internal Notifications

**Initial Alert:**
```
🚨 SEV-1: Database Outage
Status: Investigating
Impact: All services affected
ETA: TBD
```

**Update:**
```
🔄 Database Outage - Update
Status: Remediating
Action: Restarting database instance
ETA: 15 minutes
```

**Resolution:**
```
✅ Database Outage - Resolved
Status: Healthy
Duration: 25 minutes
Root Cause: Connection pool exhaustion
```

### Customer-Facing

**Status Page:**
- "We're experiencing database connectivity issues. Investigating."
- "Database issues resolved. Services returning to normal."

---

## Post-Incident Actions

### Immediate Follow-Up

- [ ] Document incident in incident log
- [ ] Create postmortem ticket
- [ ] Update monitoring/alerting if gaps found
- [ ] Review connection pool configuration

### Long-Term Improvements

- [ ] Implement connection pooling (PgBouncer)
- [ ] Add read replicas for read-heavy workloads
- [ ] Optimize slow queries
- [ ] Review and adjust connection pool sizes
- [ ] Implement circuit breakers for database calls

---

## Related Runbooks

- `RB-DB-002`: Database Migration Rollback
- `RB-DB-003`: Database Restore from Backup
- `RB-SVC-001`: Service Crash Recovery
- `RB-DR-001`: Disaster Recovery

---

## Appendix

### Database Connection Commands

```bash
# Connect to database
psql -h <host> -U <user> -d hub

# Check version
psql -h <host> -U <user> -d hub -c "SELECT version();"

# List databases
psql -h <host> -U <user> -l

# Check connections
psql -h <host> -U <user> -d hub -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';"
```

### Useful Queries

```sql
-- Check database size
SELECT pg_size_pretty(pg_database_size('hub'));

-- Check table sizes
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan DESC;
```

