# RB-DR-001 — RDS Restore Verification Drill

**Owner**: Infrastructure Engineering  
**Severity**: P1 (quarterly drill)  
**Cadence**: Quarterly (March, June, September, December)

## Overview

Validates that the latest automated RDS snapshot can be restored to a working
state within the platform RTO of 4 hours. Uses `scripts/dr/restore_verify_rds.sh`
to automate the full lifecycle: restore → migrate → health-check → teardown.

## Prerequisites

- AWS CLI configured with `rds:*` permissions on the target account
- `jq` installed (`brew install jq` / `apt-get install jq`)
- `RDS_INSTANCE_IDENTIFIER` env var set (defaults to `meshant-staging-postgres`)
- Database credentials in `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`
- No active production incidents (drill consumes snapshot quota)

## Step-by-Step

### 1. Pre-Flight Checks

```bash
# Verify AWS access
aws rds describe-db-instances --db-instance-identifier $RDS_INSTANCE_IDENTIFIER --query "DBInstances[0].DBInstanceStatus"

# Verify latest snapshot exists
aws rds describe-db-snapshots --db-instance-identifier $RDS_INSTANCE_IDENTIFIER --snapshot-type automated --query "reverse(sort_by(DBSnapshots,&SnapshotCreateTime))[0].DBSnapshotIdentifier"

# Dry run
scripts/dr/restore_verify_rds.sh --dry-run
```

### 2. Execute Drill

```bash
# Full drill with 600s RTO target
scripts/dr/restore_verify_rds.sh --target-rto-seconds 600

# Extended RTO for large snapshots
scripts/dr/restore_verify_rds.sh --target-rto-seconds 1200
```

### 3. Collect Evidence

The script outputs a JSON report:
```json
{
  "drill": "rds-restore-verify",
  "source_instance": "meshant-staging-postgres",
  "snapshot_id": "rds:meshant-staging-postgres-2026-05-20-03-00",
  "rto_seconds": 387,
  "target_rto_seconds": 600,
  "rto_within_target": true
}
```

Save this to `docs/operations/dr-drill-reports/$(date +%Y-%m)/`.

### 4. Rollback Steps

The script tears down the temp instance automatically. Manual cleanup:
```bash
# If script was interrupted, clean up any lingering temp instances
aws rds describe-db-instances --query "DBInstances[?starts_with(DBInstanceIdentifier,'dr-restore-verify-')].DBInstanceIdentifier" --output text | xargs -I{} aws rds delete-db-instance --db-instance-identifier {} --skip-final-snapshot
```

## Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| "No automated snapshot found" | Backup window hasn't run yet | Check RDS backup window; may need to wait |
| "Restore failed" | Snapshot quota exceeded | Check `aws rds describe-account-attributes` for snapshot quota |
| "Migrate failed" | Schema drift from snapshot version | Check migration dependency chain; may need `--fake-initial` |
| "Health check failed" | App doesn't start with temp DB | Check DATABASE_URL format; verify app health endpoint |
| "RTO exceeded" | Snapshot too large for db.t4g.small | Increase instance class or target RTO |

## Metrics

- **RTO (Recovery Time Objective)**: time from snapshot selection to health check pass
- **Snapshot age**: time since last automated snapshot (should be <24h per RPO)
- **Drill pass rate**: percentage of quarterly drills within RTO target

## SLA

- RTO target: 4 hours (14,400 seconds) — platform-wide
- Drill target: 10 minutes (600 seconds) — for db.t4g.small restore
- RPO: 1 hour for RDS (automated snapshots every hour in production)

## Escalation

1. **Drill fails** → Infrastructure Engineering investigates within 1 business day
2. **Two consecutive quarterly drills fail** → Escalate to VP Engineering; allocate sprint for RTO remediation
3. **RTO exceeds platform target (4h)** → Escalate to CTO; trigger incident response
