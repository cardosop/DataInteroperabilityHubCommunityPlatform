# RB-DB-003: Database Restore from Backup

**Runbook ID:** `RB-DB-003`  
**Title:** Database Restore from Backup  
**Last Updated:** 2025-01-15  
**Version:** 1.0

---

## Scope

This runbook covers restoring the primary database from a backup snapshot or point-in-time recovery.

**In Scope:**
- Full database restore
- Point-in-time recovery (PITR)
- Partial restore (specific tables/schemas)
- Restore from cloud-managed database snapshots

**Out of Scope:**
- Data migration between environments
- Database replication setup
- Backup creation procedures

---

## Prerequisites

**Tools Required:**
- `psql` (PostgreSQL client)
- `pg_dump` / `pg_restore` (for file-based backups)
- Cloud provider CLI (AWS, GCP, Azure)
- `kubectl` (for service management)

**Access Required:**
- Database superuser or restore privileges
- Backup storage access (S3, GCS, Azure Blob)
- Kubernetes cluster access
- Maintenance window approval (for full restore)

**Backup Requirements:**
- Backup ID or timestamp
- Backup location and access credentials
- Encryption keys (if applicable)

---

## Pre-Restore Assessment

### Step 1: Identify Restore Reason

**Common Reasons:**
- Data corruption
- Accidental deletion
- Point-in-time recovery required
- Disaster recovery (full restore)
- Testing/development environment setup

### Step 2: Determine Restore Target

**Full Restore:**
- Restore entire database to a specific point in time
- Requires service downtime
- Use when entire database is affected

**Partial Restore:**
- Restore specific tables or schemas
- May allow services to continue running
- Use when only specific data is affected

**Point-in-Time Recovery (PITR):**
- Restore to a specific timestamp
- Requires WAL (Write-Ahead Log) files
- Use when exact recovery time is known

### Step 3: Verify Backup Availability

**List Available Backups:**
```bash
# AWS S3 example
aws s3 ls s3://backup-bucket/db-backups/

# GCP Cloud Storage
gsutil ls gs://backup-bucket/db-backups/

# Local backups
ls -lh /backups/db/
```

**Verify Backup Integrity:**
```bash
# Check backup file checksum (if available)
md5sum backup-file.dump
sha256sum backup-file.dump
```

---

## Full Restore Procedure

### Step 1: Stop Services

**Stop All Database-Connected Services:**
```bash
# Kubernetes example
kubectl scale deployment api-service --replicas=0 -n production
kubectl scale deployment worker-service --replicas=0 -n production
kubectl scale deployment dq-service --replicas=0 -n production
kubectl scale deployment compliance-service --replicas=0 -n production
```

**Verify No Active Connections:**
```sql
SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';
-- Should be 0 or only system connections
```

### Step 2: Backup Current State

**Create Safety Snapshot:**
```bash
# PostgreSQL dump
pg_dump -Fc -h <db-host> -U <admin-user> hub > current_state_backup_$(date +%Y%m%d_%H%M%S).dump

# Store in separate location
aws s3 cp current_state_backup.dump s3://backup-bucket/safety-snapshots/
```

### Step 3: Restore from Snapshot

#### Option A: PostgreSQL pg_restore

```bash
# Download backup from object storage
aws s3 cp s3://backup-bucket/db-backups/hub-2025-01-15-02-00-00.dump ./restore.dump

# Drop existing database (CAUTION: Destructive)
psql -h <db-host> -U postgres -c "DROP DATABASE IF EXISTS hub;"

# Create new database
psql -h <db-host> -U postgres -c "CREATE DATABASE hub;"

# Restore from backup
pg_restore -h <db-host> -U <admin-user> -d hub --verbose restore.dump
```

#### Option B: Cloud-Managed Database Restore

**AWS RDS:**
```bash
aws rds restore-db-instance-from-db-snapshot \
  --db-instance-identifier hub-restored \
  --db-snapshot-identifier hub-snapshot-2025-01-15-02-00-00
```

**GCP Cloud SQL:**
```bash
gcloud sql backups restore <backup-id> \
  --backup-instance=hub-db-instance \
  --restore-instance=hub-restored
```

**Azure Database:**
```bash
az postgres server restore \
  --resource-group <resource-group> \
  --name hub-restored \
  --source-server hub-db \
  --restore-point-in-time "2025-01-15T02:00:00Z"
```

### Step 4: Point-in-Time Recovery (PITR)

**PostgreSQL with WAL Files:**
```bash
# Restore base backup
pg_basebackup -h <backup-host> -D /var/lib/postgresql/data -U replicator -P

# Configure recovery
cat > /var/lib/postgresql/data/postgresql.conf <<EOF
restore_command = 'cp /backups/wal/%f %p'
recovery_target_time = '2025-01-15 14:30:00'
recovery_target_action = 'promote'
EOF

# Start PostgreSQL (will automatically recover)
systemctl start postgresql
```

**Cloud-Managed PITR:**
```bash
# AWS RDS
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier hub \
  --target-db-instance-identifier hub-restored \
  --restore-time 2025-01-15T14:30:00Z
```

---

## Verification

### Step 1: Database Connectivity

```bash
# Test connection
psql -h <db-host> -U <admin-user> -d hub -c "SELECT version();"

# Verify database exists
psql -h <db-host> -U <admin-user> -l | grep hub
```

### Step 2: Schema Verification

```sql
-- Check table counts
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables 
ORDER BY schemaname, tablename;

-- Compare with expected counts (from monitoring/metrics)
```

### Step 3: Data Integrity

```sql
-- Check foreign key constraints
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE contype = 'f' AND NOT convalidated;

-- Check for orphaned records (example)
SELECT COUNT(*) FROM datasets 
WHERE asset_id NOT IN (SELECT id FROM assets);

-- Verify critical data
SELECT COUNT(*) FROM tenants WHERE status = 'ACTIVE';
SELECT COUNT(*) FROM audit_events WHERE occurred_at > NOW() - INTERVAL '1 day';
```

### Step 4: Application Compatibility

```bash
# Run Django checks
python manage.py check --database default

# Verify migrations
python manage.py showmigrations

# Run smoke tests
make smoke-test-production
```

---

## Post-Restore Actions

### Step 1: Update Configuration

**If Restored to New Instance:**
```bash
# Update connection strings in secrets manager
aws secretsmanager update-secret \
  --secret-id hub-db-connection \
  --secret-string '{"host": "new-db-host", "port": 5432, ...}'

# Update Kubernetes ConfigMaps/Secrets
kubectl create secret generic db-credentials \
  --from-literal=host=new-db-host \
  --from-literal=port=5432 \
  -n production --dry-run=client -o yaml | kubectl apply -f -
```

### Step 2: Re-enable Services

```bash
# Gradually scale services back up
kubectl scale deployment/api-service --replicas=1 -n production
# Wait for health check
kubectl scale deployment/api-service --replicas=3 -n production

kubectl scale deployment/worker-service --replicas=2 -n production
```

### Step 3: Monitor for Issues

**Watch Metrics (30 minutes):**
- Error rates
- Latency metrics
- Database connection pool
- Application logs

**Check Logs:**
```bash
kubectl logs -f deployment/api-service -n production
```

---

## Partial Restore

### Restore Specific Schema

```bash
pg_restore -h <db-host> -U <admin-user> -d hub \
  --schema=audit_log \
  --verbose restore.dump
```

### Restore Specific Table

```bash
pg_restore -h <db-host> -U <admin-user> -d hub \
  --table=assets \
  --verbose restore.dump
```

**Note:** Partial restores may require:
- Temporarily disabling foreign key constraints
- Restoring dependent tables in correct order
- Manual data reconciliation after restore

---

## Rollback Procedure

**If Restore Fails:**
1. Stop services
2. Restore from pre-restore snapshot (created in Step 2)
3. Investigate restore failure:
   - Backup corruption
   - Insufficient disk space
   - Permission issues
4. Document issues and create follow-up ticket

---

## Documentation

**Record Restore Details:**
- Restore timestamp
- Backup used (ID, timestamp)
- Restore duration
- Issues encountered
- Verification results

**Update Incident Log:**
- Document restore completion
- Note any data loss or inconsistencies
- Schedule post-restore review

---

## Related Runbooks

- `RB-DB-001`: Database Outage / Degradation
- `RB-DB-002`: Database Migration Rollback
- `RB-DR-001`: Disaster Recovery

---

## Appendix

### Backup Locations

**AWS S3:**
```
s3://backup-bucket/db-backups/hub-YYYY-MM-DD-HH-MM-SS.dump
```

**GCP Cloud Storage:**
```
gs://backup-bucket/db-backups/hub-YYYY-MM-DD-HH-MM-SS.dump
```

**Local:**
```
/backups/db/hub-YYYY-MM-DD-HH-MM-SS.dump
```

### Restore Checklist

```markdown
- [ ] Identify restore reason and target
- [ ] Verify backup availability
- [ ] Stop all services
- [ ] Create safety snapshot
- [ ] Execute restore procedure
- [ ] Verify database connectivity
- [ ] Verify schema state
- [ ] Verify data integrity
- [ ] Run application checks
- [ ] Re-enable services gradually
- [ ] Monitor for 30 minutes
- [ ] Document restore details
```

