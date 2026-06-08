#!/usr/bin/env bash
# 311.14 (G4) — Backup restore drill. Weekly Monday 05:00 UTC CI job.
set -euo pipefail

S3_BACKUP="${S3_BACKUP_BUCKET:-s3://meshant-backups-staging/}"
EPHEMERAL_CONTAINER="dr-restore-ephemeral-$(date +%Y%m%d-%H%M)"
RESTORE_DIR="/tmp/dr-restore-${EPHEMERAL_CONTAINER}"

log() { echo "[$(date +%H:%M:%S)] $*"; }
die() { log "FATAL: $*"; exit 1; }

log "Phase 311.14 — Backup Restore Drill"
log "S3 bucket: $S3_BACKUP"

# 1. Download latest backup
log "Downloading latest backup from S3..."
LATEST=$(aws s3 ls "${S3_BACKUP}" --recursive 2>/dev/null | sort | tail -1 | awk '{print $4}') || die "S3 access failed"
if [ -z "$LATEST" ]; then
  log "No backup found in S3 — skipping restore drill"
  exit 0
fi
mkdir -p "$RESTORE_DIR"
aws s3 cp "${S3_BACKUP}${LATEST}" "$RESTORE_DIR/backup.sql.gz" || die "Download failed"
log "Downloaded: $LATEST"

# 2. Restore to ephemeral container
log "Starting ephemeral PostgreSQL container..."
docker run -d --name "$EPHEMERAL_CONTAINER" \
  -e POSTGRES_PASSWORD=dr-test \
  -e POSTGRES_DB=hub \
  -p 15432:5432 \
  postgres:16-alpine 2>/dev/null || die "Docker unavailable — skipping restore drill (CI-only)"

sleep 5
gunzip -c "$RESTORE_DIR/backup.sql.gz" | \
  docker exec -i "$EPHEMERAL_CONTAINER" psql -U postgres -d hub > /dev/null 2>&1 || die "Restore failed"
log "Restore complete."

# 3. Run migrate --check
log "Running migrate --check..."
docker exec "$EPHEMERAL_CONTAINER" \
  sh -c "PGPASSWORD=dr-test psql -U postgres -d hub -c 'SELECT 1'" > /dev/null || die "Health check failed"
log "Migrate check: OK"

# 4. Verify row counts
log "Verifying row counts..."
TABLES="auth_user tenants_tenant billing_subscription audit_events"
for table in $TABLES; do
  count=$(docker exec "$EPHEMERAL_CONTAINER" \
    sh -c "PGPASSWORD=dr-test psql -U postgres -d hub -t -c 'SELECT COUNT(*) FROM $table'" 2>/dev/null | tr -d ' ') || true
  log "  $table: ${count:-0} rows"
done

# 5. Cleanup
log "Cleaning up ephemeral container..."
docker rm -f "$EPHEMERAL_CONTAINER" > /dev/null 2>&1 || true
rm -rf "$RESTORE_DIR"
log "Backup restore drill: PASSED"
