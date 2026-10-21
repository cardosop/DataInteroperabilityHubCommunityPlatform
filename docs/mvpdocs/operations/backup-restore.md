# Backup & Restore

This document covers backup and restore procedures for all stateful
components of the Meshant platform: PostgreSQL, S3 file storage, and the
Fuseki triple store.

## Database Backup

### Automated Daily Backups (CronJob)

A Kubernetes CronJob (`hub-backup`) runs daily at 02:00 UTC. The job executes
`scripts/backup-postgres.sh`, which:

1. Connects to `POSTGRES_DIRECT_HOST` (bypasses PgBouncer, which is
   incompatible with `pg_dump` in transaction pooling mode).
2. Streams `pg_dump | gzip -9` to a local temp file.
3. Generates a SHA-256 manifest for integrity verification.
4. Uploads both the dump and manifest to S3 with `--sse aws:kms` encryption
   and `STANDARD_IA` storage class.
5. Verifies upload size matches the local file size.
6. Runs a retention sweep, deleting objects older than `BACKUP_RETENTION_DAYS`
   (default: 30 days).

Configuration in `helm/values.yaml`:

```yaml
backup:
  enabled: true
  schedule: "0 2 * * *"
  postgresDirectHost: "postgres"
  env:
    POSTGRES_PORT: "5432"
    POSTGRES_DB: "hub"
    POSTGRES_USER: "hub"
    BACKUP_S3_BUCKET: "hub-postgres-backups"
    BACKUP_S3_PREFIX: "postgres"
    BACKUP_RETENTION_DAYS: "30"
    AWS_DEFAULT_REGION: "us-east-1"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
```

The CronJob uses `concurrencyPolicy: Forbid` to prevent overlapping runs and
`activeDeadlineSeconds: 14400` (4 hours) as a safety timeout. If a scheduled
run is missed by more than 1 hour (`startingDeadlineSeconds: 3600`), it is
skipped rather than run late.

The backup pod runs as non-root (UID 1000) with a read-only root filesystem;
`/tmp` is mounted as an emptyDir volume for the temporary dump file.

### RDS Automated Snapshots

If running on AWS RDS, enable automated snapshots with the following settings:

- **Retention period**: 7 days (minimum for production)
- **Backup window**: 03:00-04:00 UTC (after the CronJob completes)
- **Point-in-time recovery**: Enabled (allows restore to any second within
  the retention window)
- **Multi-AZ**: Enabled for production (snapshots taken from the standby to
  avoid I/O impact on the primary)

### Manual Backup

For ad-hoc backups (before destructive migrations, major releases, etc.):

```bash
# Connect to a pod with pg_dump available
kubectl exec -it deploy/hub-api -n hub-production -- bash

# Run pg_dump against the direct host (not PgBouncer)
pg_dump -h $POSTGRES_DIRECT_HOST -U hub -d hub \
  --format=custom --compress=9 \
  -f /tmp/hub-manual-$(date +%Y%m%d-%H%M%S).dump

# Upload to S3
aws s3 cp /tmp/hub-manual-*.dump \
  s3://hub-postgres-backups/manual/ \
  --sse aws:kms --storage-class STANDARD_IA
```

## Fuseki Triple Store Backup

The Fuseki TDB2 data directory is backed up daily by a separate CronJob
(`hub-backup-fuseki-tdb2`), configured at:

```yaml
fuseki:
  backup:
    enabled: true
    schedule: "0 2 * * *"
    s3Bucket: "hub-fuseki-backups"
```

The Fuseki backup job copies the TDB2 data directory to S3. Because Fuseki
uses a StatefulSet with a PVC (`mode: pvc`), the data persists across pod
restarts. In staging, `mode: emptyDir` is acceptable since the dataset is
small and auto-populated by Django signals on asset/contract save.

## S3 File Storage Sync

User-uploaded files (data assets, compliance reports, ML artifacts) are stored
in the S3 bucket configured by `AWS_STORAGE_BUCKET_NAME` (e.g.,
`hub-files-staging-279554171209` on staging, production bucket follows the
pattern `hub-files-production-<account_id>`).

### Cross-Region Replication

For disaster recovery, enable S3 Cross-Region Replication (CRR) to a backup
bucket in a secondary AWS region:

```bash
aws s3api put-bucket-replication \
  --bucket hub-files-production-<account_id> \
  --replication-configuration file://replication-config.json
```

### Manual Sync

To create a one-time backup of all files:

```bash
aws s3 sync \
  s3://hub-files-production-<account_id> \
  s3://hub-files-backup-<account_id> \
  --sse aws:kms \
  --storage-class STANDARD_IA
```

## Restore Procedures

### Database Restore from CronJob Backup

```bash
# List available backups
aws s3 ls s3://hub-postgres-backups/postgres/ --recursive | sort -k1,2

# Download the desired backup and its manifest
aws s3 cp s3://hub-postgres-backups/postgres/<timestamp>.sql.gz /tmp/
aws s3 cp s3://hub-postgres-backups/postgres/<timestamp>.sql.gz.sha256 /tmp/

# Verify integrity
cd /tmp && sha256sum -c <timestamp>.sql.gz.sha256

# Scale down API and workers to prevent writes during restore
kubectl scale deploy hub-api --replicas=0 -n hub-production
kubectl scale deploy hub-worker --replicas=0 -n hub-production
kubectl scale deploy hub-worker-heavy --replicas=0 -n hub-production

# Restore (connect to postgres directly, not PgBouncer)
gunzip -c /tmp/<timestamp>.sql.gz | \
  psql -h <POSTGRES_DIRECT_HOST> -U hub -d hub

# Scale services back up
kubectl scale deploy hub-api --replicas=3 -n hub-production
kubectl scale deploy hub-worker --replicas=3 -n hub-production
kubectl scale deploy hub-worker-heavy --replicas=1 -n hub-production

# Verify health
curl -s https://apimeshant-internal.example.com/health/ | jq .
```

### Database Restore from RDS Snapshot

1. In the AWS Console, navigate to RDS > Snapshots.
2. Select the desired snapshot and choose "Restore snapshot".
3. Use the same instance class and VPC configuration as the original.
4. Once the new instance is available, update `POSTGRES_DIRECT_HOST` in the
   Helm values or ExternalSecrets to point to the new endpoint.
5. Run `helm upgrade` to propagate the change, then verify health.

### Database Point-in-Time Recovery

```bash
aws rds restore-db-instance-to-point-in-time \
  --source-db-instance-identifier hub-production \
  --target-db-instance-identifier hub-production-pitr \
  --restore-time "2026-04-09T10:30:00Z" \
  --db-instance-class db.r6g.large
```

### File Restore from S3

```bash
# Restore all files from the backup bucket
aws s3 sync \
  s3://hub-files-backup-<account_id> \
  s3://hub-files-production-<account_id> \
  --sse aws:kms

# Or restore a specific prefix
aws s3 sync \
  s3://hub-files-backup-<account_id>/tenant/<tenant_id>/ \
  s3://hub-files-production-<account_id>/tenant/<tenant_id>/ \
  --sse aws:kms
```

## Restore Drill

Perform a quarterly restore drill to validate backup integrity and ensure the
team is familiar with the procedure. Schedule the drill during a low-traffic
window.

### Drill Procedure

1. **Select a backup**: Choose the most recent daily backup (CronJob dump).
2. **Provision a test database**: Create a temporary RDS instance or use a
   local PostgreSQL container.
3. **Restore the backup**: Follow the restore procedure above against the
   test database.
4. **Verify data integrity**:
   - Check row counts for critical tables (`assets`, `contracts`, `tenants`,
     `users`).
   - Run a sample of read queries to confirm data is accessible.
   - Verify S3 file references resolve correctly.
5. **Record results**: Document the drill date, time-to-restore, any issues
   encountered, and corrective actions in the team wiki.
6. **Clean up**: Terminate the test database instance.

### Drill Checklist

- [ ] CronJob backup dump restores without errors
- [ ] SHA-256 manifest matches the downloaded dump
- [ ] Row counts match expected values (within 24h of backup time)
- [ ] Application health check passes against restored database
- [ ] Fuseki TDB2 restore produces valid SPARQL query results
- [ ] S3 file sync completes without errors
- [ ] Time-to-restore documented (target: < 1 hour for database)
