#!/usr/bin/env bash
# 300.1 — Automated RDS snapshot restore + verification drill.
#
# Usage:
#   scripts/dr/restore_verify_rds.sh [--dry-run] [--target-rto-seconds 600]
#
# Workflow:
#   1. Identify latest automated RDS snapshot
#   2. Restore to a temp instance (db.t4g.small for cost)
#   3. Wait for instance to become available
#   4. Run Django migrate against the temp instance
#   5. Run health-check against the temp instance
#   6. Report RTO as JSON to stdout
#   7. Tear down temp instance
#   8. Exit non-zero if RTO > target
#
# Prerequisites:
#   - AWS CLI installed and configured with rds:CreateDBInstance,
#     rds:DeleteDBInstance, rds:DescribeDBInstances,
#     rds:DescribeDBSnapshots permissions
#   - jq installed
#   - DATABASE_URL env var or RDS_INSTANCE_IDENTIFIER set
#
set -euo pipefail

DRY_RUN=false
TARGET_RTO_SECONDS=600
RDS_INSTANCE="${RDS_INSTANCE_IDENTIFIER:-meshant-staging-postgres}"
TEMP_INSTANCE="dr-restore-verify-$(date +%Y%m%d-%H%M%S)"
SNAPSHOT_ID=""
START_TIME=$(date +%s)

log()  { echo "[$(date +%H:%M:%S)] $*" >&2; }
die()  { log "FATAL: $*"; exit 1; }

# ── Parse args ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run) DRY_RUN=true; shift ;;
        --target-rto-seconds) TARGET_RTO_SECONDS="$2"; shift 2 ;;
        *) die "Unknown arg: $1" ;;
    esac
done

log "Phase 300 DR Drill — RDS restore verification"
log "Source instance: $RDS_INSTANCE"
log "Target RTO: ${TARGET_RTO_SECONDS}s"

# ── 1. Identify latest snapshot ─────────────────────────────────────────
SNAPSHOT_ID=$(aws rds describe-db-snapshots \
    --db-instance-identifier "$RDS_INSTANCE" \
    --snapshot-type automated \
    --query "reverse(sort_by(DBSnapshots,&SnapshotCreateTime))[0].DBSnapshotIdentifier" \
    --output text 2>/dev/null) || die "Failed to describe snapshots for $RDS_INSTANCE"

if [[ -z "$SNAPSHOT_ID" || "$SNAPSHOT_ID" == "None" ]]; then
    die "No automated snapshot found for $RDS_INSTANCE"
fi
log "Latest snapshot: $SNAPSHOT_ID"

# ── 2. Restore to temp instance ─────────────────────────────────────────
if $DRY_RUN; then
    log "DRY RUN — would restore $SNAPSHOT_ID → $TEMP_INSTANCE"
    log "DRY RUN — would run migrate + health check, then tear down"
    log "DRY RUN PASSED (no resources created)"
    exit 0
fi

log "Restoring $SNAPSHOT_ID → $TEMP_INSTANCE (db.t4g.small)..."
aws rds restore-db-instance-from-db-snapshot \
    --db-instance-identifier "$TEMP_INSTANCE" \
    --db-snapshot-identifier "$SNAPSHOT_ID" \
    --db-instance-class db.t4g.small \
    --no-publicly-accessible \
    --tags "Key=purpose,Value=dr-drill" "Key=ttl_hours,Value=2" \
    > /dev/null || die "Restore failed"

# ── 3. Wait for available ───────────────────────────────────────────────
log "Waiting for $TEMP_INSTANCE to become available..."
aws rds wait db-instance-available \
    --db-instance-identifier "$TEMP_INSTANCE" || die "Timeout waiting for instance"

ENDPOINT=$(aws rds describe-db-instances \
    --db-instance-identifier "$TEMP_INSTANCE" \
    --query "DBInstances[0].Endpoint.Address" --output text)
log "Temp endpoint: $ENDPOINT"

# ── 4. Run migrate ──────────────────────────────────────────────────────
TEMP_DB_URL="postgresql://${POSTGRES_USER:-hub}:${POSTGRES_PASSWORD:-hub}@${ENDPOINT}:5432/${POSTGRES_DB:-hub}"
log "Running migrate against temp instance..."
if ! DATABASE_URL="$TEMP_DB_URL" python hub/manage.py migrate --noinput 2>&1 | tail -5; then
    RESTORE_TIME=$(($(date +%s) - START_TIME))
    log "Migrate failed — tearing down $TEMP_INSTANCE"
    aws rds delete-db-instance \
        --db-instance-identifier "$TEMP_INSTANCE" \
        --skip-final-snapshot > /dev/null 2>&1 || true
    die "Migrate failed after ${RESTORE_TIME}s"
fi

# ── 5. Health check ─────────────────────────────────────────────────────
log "Running health check against temp instance..."
HEALTH_URL="http://${ENDPOINT}:8000/api/v1/health/"
if ! curl -sf --max-time 30 "$HEALTH_URL" > /dev/null 2>&1; then
    RESTORE_TIME=$(($(date +%s) - START_TIME))
    log "Health check failed — tearing down $TEMP_INSTANCE"
    aws rds delete-db-instance \
        --db-instance-identifier "$TEMP_INSTANCE" \
        --skip-final-snapshot > /dev/null 2>&1 || true
    die "Health check failed after ${RESTORE_TIME}s"
fi

RESTORE_TIME=$(($(date +%s) - START_TIME))
log "Restore + migrate + health check: ${RESTORE_TIME}s"

# ── 6. Report RTO ───────────────────────────────────────────────────────
cat <<JSON
{
  "drill": "rds-restore-verify",
  "source_instance": "$RDS_INSTANCE",
  "snapshot_id": "$SNAPSHOT_ID",
  "temp_instance": "$TEMP_INSTANCE",
  "rto_seconds": $RESTORE_TIME,
  "target_rto_seconds": $TARGET_RTO_SECONDS,
  "rto_within_target": $([ $RESTORE_TIME -le $TARGET_RTO_SECONDS ] && echo true || echo false),
  "timestamp": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
JSON

# ── 7. Tear down ────────────────────────────────────────────────────────
log "Tearing down $TEMP_INSTANCE..."
aws rds delete-db-instance \
    --db-instance-identifier "$TEMP_INSTANCE" \
    --skip-final-snapshot > /dev/null 2>&1 || true
log "Teardown complete."

# ── 8. Exit non-zero if RTO exceeded ────────────────────────────────────
if [ $RESTORE_TIME -gt $TARGET_RTO_SECONDS ]; then
    log "RTO EXCEEDED: ${RESTORE_TIME}s > ${TARGET_RTO_SECONDS}s target"
    exit 1
fi

log "DRILL PASSED — RTO ${RESTORE_TIME}s within ${TARGET_RTO_SECONDS}s target"
