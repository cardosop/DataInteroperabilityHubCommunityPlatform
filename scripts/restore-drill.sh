#!/usr/bin/env bash
# =============================================================================
# restore-drill.sh — Quarterly automated backup-restore drill.
#
# Restores the latest S3 backup to a TEMPORARY database (NOT the
# production database), verifies critical table row counts, logs
# the elapsed time against RTO (4h) + RPO (24h) targets, and
# cleans up the temp database.
#
# Schedule: quarterly (0 2 1 */3 *) via K8s CronJob or system crontab.
# Run with: DRY_RUN=1 ./scripts/restore-drill.sh  (tests S3 access only)
#
# Exit codes:
#   0 — restore drill succeeded, all health checks passed, within RTO
#   1 — S3 access / credential failure
#   2 — pg_restore failed
#   3 — health checks failed
#   4 — RTO exceeded (restore took >4h)
# =============================================================================
set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
DRILL_STARTED=$(date -u +%s)

# ── Configuration ────────────────────────────────────────────────────────────
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET required}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_DEFAULT_REGION

# The drill uses a TEMPORARY database — never the production database.
POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
DRILL_DB="restore_drill_$(date +%Y%m%d_%H%M%S)"
export PGPASSWORD="${PGPASSWORD:-}"

DRILL_DIR="${DRILL_DIR:-/tmp/restore_drill_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$DRILL_DIR"
cd "$DRILL_DIR"

RTO_SECONDS=$((4 * 3600))  # 4 hours
RPO_SECONDS=$((24 * 3600)) # 24 hours

_psql() { psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$@"; }

timestamp() { date -u +%Y-%m-%dT%H:%M:%SZ; }

log() { echo "[$(timestamp)] $*"; }

# ── Dry-run mode ─────────────────────────────────────────────────────────────
if [ "$DRY_RUN" = "1" ]; then
    log "DRY RUN — verifying S3 access only (no restore)"
    LATEST=$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/" \
        | grep 'PRE ' | awk '{print $2}' | sed 's|/||' | sort | tail -1)
    if [ -z "$LATEST" ]; then
        log "ERROR: No backups found in S3" >&2
        exit 1
    fi
    BACKUP_AGE=$(( $(date -u +%s) - $(date -u -d "${LATEST:0:10}" +%s 2>/dev/null || date -u +%s) ))
    log "Latest backup: $LATEST (age: ${BACKUP_AGE}s, RPO target: ${RPO_SECONDS}s)"
    if [ "$BACKUP_AGE" -gt "$RPO_SECONDS" ]; then
        log "WARNING: Latest backup age (${BACKUP_AGE}s) exceeds RPO (${RPO_SECONDS}s)"
    fi
    log "DRY RUN PASSED — S3 accessible, latest backup found"
    exit 0
fi

# ── 1. Resolve latest backup ────────────────────────────────────────────────
log "== Resolving latest backup ..."
BACKUP_TIMESTAMP=$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/" \
    | grep 'PRE ' | awk '{print $2}' | sed 's|/||' | sort | tail -1)
if [ -z "$BACKUP_TIMESTAMP" ]; then
    log "ERROR: No backups found" >&2
    exit 1
fi

BACKUP_AGE=$(( $(date -u +%s) - $(date -u -d "${BACKUP_TIMESTAMP:0:10}" +%s 2>/dev/null || echo 0) ))
log "   Backup: $BACKUP_TIMESTAMP (age: ${BACKUP_AGE}s)"
if [ "$BACKUP_AGE" -gt "$RPO_SECONDS" ]; then
    log "   WARNING: Backup age exceeds RPO ($RPO_SECONDS s)"
fi

# ── 2. Download + verify ────────────────────────────────────────────────────
S3_PATH="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${BACKUP_TIMESTAMP}"
log "== Downloading backup from $S3_PATH ..."
aws s3 cp "${S3_PATH}/backup.sql.gz" ./backup.sql.gz || { log "ERROR: S3 download failed" >&2; exit 1; }
aws s3 cp "${S3_PATH}/backup.sql.gz.sha256" ./backup.sql.gz.sha256 || { log "ERROR: Manifest download failed" >&2; exit 1; }

EXPECTED=$(cat backup.sql.gz.sha256 | awk '{print $1}')
ACTUAL=$(sha256sum backup.sql.gz | awk '{print $1}')
if [ "$EXPECTED" != "$ACTUAL" ]; then
    log "ERROR: SHA-256 mismatch" >&2
    exit 1
fi
log "   SHA-256 OK"

# ── 3. Restore to temp database ─────────────────────────────────────────────
log "== Restoring to temp database: $DRILL_DB ..."
_psql -d postgres -c "CREATE DATABASE $DRILL_DB ENCODING 'UTF8'" 2>/dev/null || {
    log "ERROR: Could not create temp database $DRILL_DB" >&2
    exit 2
}

gunzip -c backup.sql.gz | _psql -d "$DRILL_DB" -v ON_ERROR_STOP=1 2>&1 || {
    log "ERROR: pg_restore to $DRILL_DB failed" >&2
    _psql -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" 2>/dev/null || true
    exit 2
}

# ── 4. Health checks ────────────────────────────────────────────────────────
log "== Running health checks on $DRILL_DB ..."
CRITICAL_TABLES=("tenants" "users" "django_migrations" "assets_asset" "audit_events")
HEALTH_FAIL=0
for table in "${CRITICAL_TABLES[@]}"; do
    count=$(_psql -d "$DRILL_DB" -tAc "SELECT COUNT(*) FROM $table" 2>/dev/null || echo 0)
    log "   $table: $count rows"
    if [ "${count:-0}" -eq 0 ]; then
        log "   WARNING: $table is empty"
        HEALTH_FAIL=1
    fi
done

# ── 5. Verify migrations match ──────────────────────────────────────────────
MIGRATIONS_COUNT=$(_psql -d "$DRILL_DB" -tAc "SELECT COUNT(*) FROM django_migrations" 2>/dev/null || echo 0)
log "   django_migrations: $MIGRATIONS_COUNT rows"

# ── 6. Cleanup temp database ────────────────────────────────────────────────
log "== Cleaning up temp database $DRILL_DB ..."
_psql -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DRILL_DB' AND pid <> pg_backend_pid()" 2>/dev/null || true
_psql -d postgres -c "DROP DATABASE IF EXISTS $DRILL_DB" 2>/dev/null || true
rm -f backup.sql.gz backup.sql.gz.sha256

# ── 7. Timing ───────────────────────────────────────────────────────────────
DRILL_ENDED=$(date -u +%s)
DRILL_DURATION=$((DRILL_ENDED - DRILL_STARTED))
log "== Drill complete in ${DRILL_DURATION}s (RTO target: ${RTO_SECONDS}s)"

# ── 8. Report ────────────────────────────────────────────────────────────────
if [ "$HEALTH_FAIL" -ne 0 ]; then
    log "RESULT: FAIL — health checks failed"
    exit 3
fi
if [ "$DRILL_DURATION" -gt "$RTO_SECONDS" ]; then
    log "RESULT: PASS (health) + RTO_EXCEEDED — restore took ${DRILL_DURATION}s vs RTO ${RTO_SECONDS}s"
    exit 4
fi
log "RESULT: PASS — restore drill succeeded within RTO"
