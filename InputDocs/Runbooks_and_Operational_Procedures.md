# Runbooks & Operational Procedures (MVP)

This document defines the **minimum structure and content** for operational runbooks covering:

- Common failures (DB down, queue full, service crash).
- Deployment procedures.
- Data recovery.
- Security incidents.

Runbooks are living documents and MUST be kept up to date with each major release.

---

## 1. Runbook Specifications

### 1.1 Runbook structure (template)

Every runbook MUST follow this structure:

1. **Title & ID**
   - Clear, unique name (e.g., `RB-DB-001 Database Outage`).
2. **Scope**
   - What systems are in scope.
   - What is explicitly out of scope.
3. **Audience & Roles**
   - Who is expected to use this (on-call SRE, app engineer, security team).
   - Required permissions (DB admin, cloud console, etc.).
4. **Prerequisites**
   - Tools and access needed (VPN, kubectl, psql, cloud console).
   - Links to dashboards and logs.
5. **Symptoms**
   - How this issue typically surfaces:
     - Alert names.
     - User reports / error messages.
     - Example log snippets.
6. **Impact**
   - User-visible impact (which flows broken, data at risk).
   - Severity guidance (SEV-1/2/3).
7. **Detection & Diagnosis**
   - Step-by-step checks:
     - Dashboards to look at (metrics, latency, error rates).
     - Log queries / commands.
     - How to confirm root cause vs. similar issues.
8. **Immediate Actions (“First 10 Minutes”)**
   - Concrete, ordered steps:
     - What to restart / fail over.
     - What to disable temporarily (e.g., job submission).
     - When to put system into “maintenance mode”.
9. **Remediation Procedures**
   - Detailed steps to restore normal operation.
   - Alternative / degraded modes (e.g., read-only).
   - Rollback or failover procedures if remediation fails.
10. **Communication**
    - Who to notify (internal channels, incident room).
    - What to tell support / customer-facing teams.
    - Templates for status messages.
11. **Validation & Recovery**
    - How to confirm system is healthy again:
      - Metrics targets, error rate thresholds, smoke tests.
12. **Post-Incident Actions**
    - What to capture for PIR / postmortem.
    - Tickets / follow-up tasks (tech debt, improvements).

All runbooks MUST link to:

- Relevant **dashboards** (metrics, logs, traces).
- Relevant **config / infra docs** (DB topology, queue configs, deployment pipelines).

---

### 1.2 Runbook: common failures

This section defines the minimum required runbooks for common technical failures.

#### 1.2.1 Database down / degraded

**Runbook ID:** `RB-DB-001`  
**Title:** Database Outage / Degradation

Key sections (in addition to the generic template in §1.1):

- **Symptoms**
  - DB connection errors in logs (`connection refused`, `too many connections`, `timeout`).
  - API error spikes (5xx), elevated latency on DB-backed endpoints.
  - Alerts:
    - `db_availability_critical`
    - `db_connection_pool_exhausted`
    - `db_query_latency_high`
- **Diagnosis**
  - Check DB health dashboard (CPU, connections, storage, I/O).
  - Check cloud provider / managed DB status.
  - Distinguish:
    - Full outage vs.
    - Connection pool exhaustion vs.
    - Specific node/replica failure.
- **Immediate actions**
  - If DB is fully down:
    - Page DB/on-call immediately.
    - Put system into read-only or maintenance mode if supported.
  - If connection pool exhausted:
    - Temporarily scale API/worker replicas down or reduce max concurrency.
    - Identify noisy tenants or endpoints causing overload.
- **Remediation**
  - Restart failed DB instances / fail over to replica where supported.
  - Scale up DB or adjust connection pool sizes if needed.
  - Throttle or temporarily disable non-critical background jobs.
- **Validation**
  - DB metrics back within normal thresholds.
  - API p95 latency and error rates back to baseline.
  - Core paths pass smoke tests.

---

#### 1.2.2 Queue full / high backlog

**Runbook ID:** `RB-QUEUE-001`  
**Title:** Queue Backlog / Throttling

Key sections:

- **Symptoms**
  - Alerts: `queue_depth_high`, `job_lag_high`, `queue_throttling_detected`.
  - Jobs stuck in `PENDING` for long periods.
- **Diagnosis**
  - Check queue depth and age of oldest messages.
  - Check worker health (CPU, error rate).
  - Determine if backlog is:
    - Organic load spike.
    - Worker failure.
    - Downstream dependency causing retries.
- **Immediate actions**
  - Pause non-critical job producers (batch, low-priority tenants).
  - If workers crashed → restart or scale out.
  - If downstream dependency broken → stop sending affected jobs.
- **Remediation**
  - Scale workers horizontally and/or vertically.
  - Tune per-tenant/job-type rate limits.
  - Drain queue in controlled fashion (prioritize critical jobs).
- **Validation**
  - Queue depth trending down.
  - Job lag back under target (see Testing Strategy job lag thresholds).

---

#### 1.2.3 Service crash / degraded

**Runbook ID:** `RB-SVC-001`  
**Title:** Service Crash / High Error Rate

Key sections:

- **Symptoms**
  - Alerts: `service_5xx_rate_high`, `service_latency_high`, pod restarts.
  - Logs with OOM, panic/stack traces.
- **Diagnosis**
  - Check service dashboards (CPU, memory, restarts).
  - Inspect recent deploys (was there a rollout?).
  - Look at logs around first failure.
- **Immediate actions**
  - If a recent deployment correlates:
    - Consider rolling back to previous version.
  - If resource exhaustion:
    - Temporarily scale replicas or limits.
  - For critical endpoints:
    - Enable feature flags / kill switches to reduce load.
- **Remediation**
  - Roll back / roll forward with fix.
  - Apply configuration changes (timeouts, circuit breakers, caches) if needed.
- **Validation**
  - Error rate back within thresholds.
  - Latency normalized.
  - No ongoing crash loops.

---

### 1.3 Runbook: deployment procedures

**Runbook ID:** `RB-DEPLOY-001`  
**Title:** Standard Deployment Procedure

Scope: routine application releases in staging and production.

Key sections:

- **Pre-checks**
  - All tests green (unit, integration, migration tests).
  - Change tickets approved as required.
  - No active SEV-1/SEV-2 incidents.
- **Deployment steps**
  - How to trigger deploy (CI/CD pipeline, manual commands).
  - Sequence:
    - Deploy to staging → run smoke tests.
    - Canary or partial rollout in production.
    - Full rollout after canary passes.
- **Health checks**
  - Which dashboards to watch during deploy.
  - Error/latency thresholds that force rollback.
- **Rollback procedure**
  - How to revert to previous version:
    - Previous image tag, helm chart version, etc.
  - How to verify rollback succeeded.

**Database Migration Rollback Procedure**

**Runbook ID:** `RB-DB-002`  
**Title:** Database Migration Rollback (Failed Migration)

**Scope**: Rolling back a failed database migration in production.

**Prerequisites**:
- Database admin access (read/write).
- Access to migration tool (Flyway, Alembic, etc.).
- Backup/snapshot of database before migration (if available).
- Migration scripts and version history.

**Procedure**:

1. **Assess the failure**:
   - Check migration tool logs to identify which migration failed and at what step.
   - Determine if migration partially applied (some DDL executed, some not).
   - Check database state: Which tables/columns/indexes were created/modified?

2. **Decision: Rollback vs. Forward Fix**:
   - **If migration is fully reversible** (e.g., adding nullable columns, creating new tables):
     - Proceed with rollback procedure below.
   - **If migration is partially applied and not easily reversible** (e.g., data transformation, column type changes):
     - Consider forward fix: Create a new migration that repairs the state.
     - Rollback may cause data loss or inconsistency.

3. **Rollback steps (if proceeding)**:

   **Option A: Using migration tool rollback (if supported)**:
   ```bash
   # Example with Flyway (if undo migrations exist)
   flyway undo -target=<previous_version>
   ```

   **Option B: Manual SQL rollback**:
   - Identify the exact DDL statements that were executed.
   - Write reverse SQL statements:
     - `CREATE TABLE` → `DROP TABLE`
     - `ALTER TABLE ADD COLUMN` → `ALTER TABLE DROP COLUMN`
     - `CREATE INDEX` → `DROP INDEX`
   - **Execute in reverse order** of the original migration.
   - **Test rollback SQL in staging first** if possible.

4. **Verify rollback**:
   - Check migration tool version table: Should show previous version.
   - Verify schema state:
     - Run schema validation queries.
     - Check that application can connect and perform basic operations.
   - Re-run application smoke tests.

5. **Post-rollback actions**:
   - Document the rollback in incident log.
   - Create follow-up ticket to fix the migration and re-apply.
   - Update migration scripts based on lessons learned.

---

**Database Restore Procedures**

**Runbook ID:** `RB-DB-003`  
**Title:** Database Restore from Backup

**Scope**: Restoring the primary database from a backup snapshot or point-in-time recovery.

**Prerequisites**:
- Database admin access (superuser or restore privileges).
- Access to backup storage (S3, GCS, Azure Blob, or local backup files).
- Backup metadata (backup ID, timestamp, encryption key if applicable).
- Sufficient disk space for restore (typically 2-3x database size).
- Maintenance window or service downtime approval.

**Procedure**:

1. **Pre-restore Assessment**:
   - **Identify restore reason**:
     - Data corruption
     - Accidental deletion
     - Point-in-time recovery (PITR) required
     - Disaster recovery (full restore)
   - **Determine restore target**:
     - **Full restore**: Restore entire database to a specific point in time
     - **Partial restore**: Restore specific tables or schemas
     - **Point-in-time recovery (PITR)**: Restore to a specific timestamp
   - **Verify backup availability**:
     - List available backups: `aws s3 ls s3://backup-bucket/db-backups/` (example)
     - Verify backup integrity (checksums, if available)
     - Note backup timestamp and size

2. **Stop Services** (if full restore):
   - **Stop all services** that connect to the database:
     ```bash
     # Kubernetes example
     kubectl scale deployment api-service --replicas=0
     kubectl scale deployment worker-service --replicas=0
     # ... repeat for all services
     ```
   - **Verify no active connections**:
     ```sql
     SELECT count(*) FROM pg_stat_activity WHERE datname = 'hub';
     -- Should be 0 or only system connections
     ```
   - **Note**: For partial restores, services may continue running (with degraded functionality)

3. **Backup Current State** (safety measure):
   - **Create snapshot of current database** (even if corrupted):
     ```bash
     # PostgreSQL example
     pg_dump -Fc -h <db-host> -U <admin-user> hub > current_state_backup.dump
     ```
   - **Store snapshot** in separate location (for comparison or rollback)

4. **Restore from Snapshot** (Full Restore):

   **Option A: PostgreSQL (using pg_restore)**:
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

   **Option B: PostgreSQL (using filesystem-level restore)**:
   ```bash
   # Stop PostgreSQL service
   systemctl stop postgresql
   
   # Backup current data directory
   mv /var/lib/postgresql/data /var/lib/postgresql/data.old
   
   # Restore from filesystem snapshot
   tar -xzf /backups/hub-2025-01-15-02-00-00.tar.gz -C /var/lib/postgresql/
   
   # Start PostgreSQL service
   systemctl start postgresql
   ```

   **Option C: Cloud-managed database (AWS RDS, GCP Cloud SQL, Azure Database)**:
   - Use cloud provider console or CLI:
     ```bash
     # AWS RDS example
     aws rds restore-db-instance-from-db-snapshot \
       --db-instance-identifier hub-restored \
       --db-snapshot-identifier hub-snapshot-2025-01-15-02-00-00
     ```
   - Wait for restore to complete (typically 10-30 minutes)
   - Update connection strings to point to restored instance

5. **Point-in-Time Recovery (PITR)**:

   **PostgreSQL (using WAL files)**:
   ```bash
   # Restore base backup
   pg_basebackup -h <backup-host> -D /var/lib/postgresql/data -U replicator -P
   
   # Create recovery.conf (PostgreSQL 12+) or postgresql.conf entry
   cat > /var/lib/postgresql/data/postgresql.conf <<EOF
   restore_command = 'cp /backups/wal/%f %p'
   recovery_target_time = '2025-01-15 14:30:00'
   recovery_target_action = 'promote'
   EOF
   
   # Start PostgreSQL (will automatically recover to target time)
   systemctl start postgresql
   ```

   **Cloud-managed database**:
   - Use cloud provider PITR feature:
     ```bash
     # AWS RDS example
     aws rds restore-db-instance-to-point-in-time \
       --source-db-instance-identifier hub \
       --target-db-instance-identifier hub-restored \
       --restore-time 2025-01-15T14:30:00Z
     ```

6. **Verify Restore Integrity**:

   - **Check database connectivity**:
     ```bash
     psql -h <db-host> -U <admin-user> -d hub -c "SELECT version();"
     ```
   - **Verify schema**:
     ```sql
     -- Check table counts
     SELECT schemaname, tablename, n_live_tup 
     FROM pg_stat_user_tables 
     ORDER BY schemaname, tablename;
     
     -- Compare with expected counts (from monitoring/metrics)
     ```
   - **Verify data integrity**:
     ```sql
     -- Check foreign key constraints
     SELECT conname, conrelid::regclass, confrelid::regclass
     FROM pg_constraint
     WHERE contype = 'f' AND NOT convalidated;
     
     -- Check for orphaned records (example)
     SELECT COUNT(*) FROM datasets WHERE asset_id NOT IN (SELECT id FROM assets);
     ```
   - **Verify critical data**:
     ```sql
     -- Check tenant count
     SELECT COUNT(*) FROM tenants WHERE status = 'ACTIVE';
     
     -- Check recent audit events
     SELECT COUNT(*) FROM audit_events WHERE occurred_at > NOW() - INTERVAL '1 day';
     ```

7. **Post-Restore Actions**:

   - **Update application configuration** (if restored to new instance):
     - Update database connection strings in secrets manager
     - Update Kubernetes ConfigMaps/Secrets
     - Restart services to pick up new configuration
   - **Re-enable services**:
     ```bash
     # Kubernetes example
     kubectl scale deployment api-service --replicas=3
     kubectl scale deployment worker-service --replicas=2
     # ... repeat for all services
     ```
   - **Run smoke tests**:
     - Verify API endpoints respond correctly
     - Verify basic CRUD operations
     - Verify job processing works
   - **Monitor for issues**:
     - Watch error rates and latency metrics
     - Check application logs for database errors
     - Verify data consistency across services

8. **Rollback Procedure** (if restore fails):

   - **If restore is unsuccessful**:
     - Stop services
     - Restore from pre-restore snapshot (created in step 3)
     - Investigate restore failure (backup corruption, insufficient space, permissions)
     - Document issues and create follow-up ticket

9. **Documentation**:

   - **Record restore details**:
     - Restore timestamp
     - Backup used (ID, timestamp)
     - Restore duration
     - Issues encountered
     - Verification results
   - **Update incident log** with restore completion
   - **Schedule post-restore review** to identify root cause and prevention measures

**Partial Restore (Specific Tables/Schemas)**

For restoring specific tables or schemas without full database restore:

```bash
# Restore specific schema
pg_restore -h <db-host> -U <admin-user> -d hub \
  --schema=audit_log \
  --verbose restore.dump

# Restore specific table
pg_restore -h <db-host> -U <admin-user> -d hub \
  --table=assets \
  --verbose restore.dump
```

**Note**: Partial restores may require:
- Disabling foreign key constraints temporarily
- Restoring dependent tables in correct order
- Manual data reconciliation after restore

---

### 1.2.3 Secrets Rotation Procedures

**Runbook ID:** `RB-SEC-001`  
**Title:** Secrets Rotation (Database, API Keys, JWT Keys)

**Scope**: Rotating secrets (database passwords, API keys, JWT signing keys) without service downtime.

**Prerequisites**:
- Access to secrets manager (AWS Secrets Manager, GCP Secret Manager, HashiCorp Vault, etc.).
- Access to database admin tools (if rotating DB passwords).
- Access to Kubernetes/container orchestration platform.
- Service deployment permissions.

**General Principles**:
- Secrets rotation MUST be done in a way that allows services to continue operating during rotation.
- Old secrets MUST remain valid during a grace period (typically 24-48 hours) to allow all service instances to pick up new secrets.
- Services MUST support reading secrets from the secrets manager at startup and periodically (for hot reload if supported).

#### RB-SEC-001.1: Database Password Rotation

**Procedure**:

1. **Preparation**:
   - Identify all services that connect to the database.
   - Ensure all services are healthy and running.
   - Create a backup of the current database password (for rollback if needed).
   - Schedule rotation during low-traffic period (if possible).

2. **Generate new password**:
   - Generate a strong password (minimum 32 characters, mixed case, numbers, symbols).
   - Store new password in secrets manager with a new version/key (e.g., `db-password-v2`).

3. **Update database user password**:
   ```sql
   -- Connect as superuser
   ALTER USER hub_user WITH PASSWORD 'new_password_here';
   ```
   - Verify new password works: `psql -U hub_user -d hub -h <db-host>`.

4. **Update secrets in secrets manager**:
   - Update the primary secret key (e.g., `db-password`) to point to the new password.
   - Keep old password available under a backup key (e.g., `db-password-old`) for 48 hours.

5. **Rolling service restart**:
   - Restart services one by one (or use rolling deployment):
     ```bash
     # Kubernetes example
     kubectl rollout restart deployment/api-service
     kubectl rollout restart deployment/asset-service
     # ... repeat for all services
     ```
   - Wait for each service to become ready before restarting the next.
   - Monitor service health during restart.

6. **Verification**:
   - Check service logs for connection errors.
   - Verify all services can connect to database.
   - Run smoke tests to ensure functionality.
   - Monitor database connection metrics.

7. **Cleanup** (after 48 hours):
   - Remove old password from secrets manager.
   - Verify no services are using old password (check logs/metrics).

**Rollback** (if issues occur):
- Revert database password to old value.
- Update secrets manager to point back to old password.
- Restart affected services.

#### RB-SEC-001.2: JWT Signing Key Rotation

**Procedure**:

1. **Preparation**:
   - Identify current active key ID (`kid`) in JWKS endpoint.
   - Generate new keypair (RSA-2048 or ECDSA-P256).
   - Calculate new `kid` (e.g., UUID or key hash).

2. **Add new key to JWKS**:
   - Add new public key to JWKS endpoint (`.well-known/jwks.json`).
   - Keep old key in JWKS (for token verification during grace period).

3. **Update secrets manager**:
   - Store new private key in secrets manager (e.g., `jwt-signing-key-v2`).
   - Update primary secret key to point to new private key.

4. **Start issuing tokens with new key**:
   - Update `auth-service` to use new private key for signing.
   - New tokens will include new `kid` in header.
   - Old tokens (with old `kid`) remain valid until expiration.

5. **Rolling restart of auth-service**:
   - Restart `auth-service` instances to pick up new key.
   - Monitor token issuance and verification.

6. **Grace period** (wait for old tokens to expire):
   - Wait for maximum token lifetime (e.g., 1 hour for access tokens, 14 days for refresh tokens).
   - Monitor token verification metrics to ensure old tokens are no longer used.

7. **Remove old key** (after grace period):
   - Remove old public key from JWKS endpoint.
   - Remove old private key from secrets manager.

**Rollback** (if issues occur):
- Revert JWKS to include only old key.
- Update secrets manager to point back to old private key.
- Restart `auth-service`.

#### RB-SEC-001.3: API Key Rotation

**Procedure**:

1. **Preparation**:
   - Identify all API keys that need rotation.
   - Notify key owners (if applicable) about rotation schedule.

2. **Create new API keys**:
   - Generate new API keys for each tenant/user.
   - Store new keys in database with `status = ACTIVE`.
   - Set old keys to `status = REVOKED` (but keep in database for audit).

3. **Notify clients**:
   - Send notification to key owners with new API key.
   - Provide migration timeline (e.g., 7 days to update).

4. **Grace period**:
   - Allow both old and new keys to work during grace period (e.g., 7 days).
   - Monitor usage of old vs. new keys.

5. **Disable old keys** (after grace period):
   - Set old keys to `status = REVOKED` in database.
   - Verify no requests are using old keys.

**Rollback** (if issues occur):
- Re-activate old API keys (`status = ACTIVE`).
- Revoke new keys if needed.

#### RB-SEC-001.4: Object Storage (S3) Access Key Rotation

**Procedure**:

1. **Preparation**:
   - Identify all services using S3 access keys.
   - Generate new access key pair in S3/object storage provider.

2. **Update secrets manager**:
   - Store new access key and secret key in secrets manager.
   - Keep old keys available for grace period.

3. **Rolling service restart**:
   - Restart services that use S3 (e.g., `ingestion-service`, `worker-service`).
   - Verify services can read/write to S3.

4. **Verification**:
   - Test file upload/download operations.
   - Monitor S3 access metrics.

5. **Disable old keys** (after 48 hours):
   - Disable old access keys in S3 provider.
   - Remove old keys from secrets manager.

**Rollback** (if issues occur):
- Re-enable old access keys in S3 provider.
- Update secrets manager to point back to old keys.
- Restart affected services.

---

### 1.2.4 Service Crash Recovery
     - Run schema validation queries.
     - Check that removed objects are gone.
     - Check that restored objects exist.
   - Run application smoke tests to ensure schema matches application expectations.

5. **Post-rollback**:
   - Document the failure and rollback in incident log.
   - Fix the migration script.
   - Re-test migration in non-production environments.
   - Plan re-deployment with fixed migration.

**Note**: For migrations that include data transformations or complex state changes, rollback may not be safe. In such cases, forward-fix migrations are preferred.
- **Post-deploy**
  - Additional migrations / background jobs to confirm.
  - Logs and traces to inspect for silent failures.

Optional additional runbooks (referencing this spec):

- `RB-DEPLOY-002` Hotfix Procedure.
- `RB-DEPLOY-003` Rollback-Only Procedure.

---

### 1.4 Runbook: data recovery

**Runbook ID:** `RB-DR-001`  
**Title:** Data Recovery & Restore

Scope: recovery from:

- Accidental delete / corruption within DB.
- Object storage issues (lost/overwritten files).
- Triple-store loss or out-of-sync conditions.

Key sections:

- **Preconditions**
  - Availability of backups (DB snapshots, object storage versions).
  - Verification of backup schedules and locations.
- **Classification**
  - Identify type of data loss:
    - Single tenant vs. multi-tenant.
    - Single asset/dataset vs. whole subsystem.
- **Recovery plans**
  - **DB restore**:
    - Restore from snapshot to:
      - Isolated environment first (recommended), or
      - Directly to production for small, localized issues.
    - Apply migrations up to current schema.
    - Run consistency checks (invariants, referential integrity).
  - **File/object restore**:
    - Retrieve from object storage versioning / backup.
    - Re-link to corresponding DB records if necessary.
  - **Triple-store rebuild**:
    - Restore from snapshot.
    - Or re-run semantic mapping jobs for affected assets.
- **Minimize blast radius**
  - Consider tenant-scoped restore where possible.
  - Communicate impacted tenants and expected timelines.
- **Validation**
  - Re-run DQ/compliance or checks over recovered assets.
  - Confirm `semantic_status` / `asset_status` consistent.
- **Post-recovery**
  - Document root cause.
  - Adjust backup frequency, retention, and DR drills as needed.

---

### 1.5 Runbook: security incidents

**Runbook ID:** `RB-SEC-001`  
**Title:** Security Incident Response

Scope: suspected or confirmed security incidents, including:

- Suspected account compromise.
- Data exfiltration / unauthorized access.
- Vulnerability exploitation (e.g., injection, RCE).

Key sections:

- **Severity & classification**
  - SEV levels aligned with incident framework.
  - Criteria for declaring a security incident (vs. normal bug).
- **Immediate actions**
  - Containment:
    - Revoke affected API keys / tokens.
    - Lock suspected user accounts.
    - Temporarily block specific IP ranges or clients.
  - Evidence preservation:
    - Snapshot logs, traces, relevant DB rows.
    - Ensure no log/PII scrubbing destroys needed forensic detail (balance with privacy).
- **Investigation**
  - Log queries to identify:
    - Impacted tenants/assets.
    - Time range of suspicious activity.
    - Entry points and techniques.
  - Use of audit tables (`audit_events`, cross-tenant access logs).
- **Communication**
  - Internal:
    - Security team, legal/compliance, management.
  - External:
    - Impacted tenants (if data involved).
    - Regulators, if required by law (GDPR, etc.).
  - Provide templates for:
    - Initial notification,
    - Follow-up updates,
    - Final incident report.
- **Eradication & recovery**
  - Patch vulnerabilities.
  - Rotate keys/secrets as needed.
  - Validate that the attacker’s access is fully removed.
- **Post-incident**
  - Full root cause analysis and remediation plan.
  - Update:
    - Security controls.
    - Monitoring/alerting.
    - This runbook, if gaps were found.

---

These specifications define **what each runbook must contain**. The actual runbook documents (`RB-DB-001`, `RB-QUEUE-001`, etc.) should live as separate, concrete pages/playbooks that reference this document and follow its template.
