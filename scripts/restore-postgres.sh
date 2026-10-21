#!/usr/bin/env bash
# =============================================================================
# restore-postgres.sh — Production PostgreSQL restore from S3 backup
#
# Pipeline:
#   1. Download backup + manifest from S3 (latest if no BACKUP_TIMESTAMP given)
#   2. SHA-256 verification against manifest
#   3. Terminate active connections to target database
#   4. Drop + recreate target database
#   5. pg_restore into fresh database
#   6. Run post-restore health checks (row counts on critical tables)
#   7. Run Django migrations to ensure schema is current
#
# Usage:
#   ./scripts/restore-postgres.sh                        # restore latest backup
#   ./scripts/restore-postgres.sh 2026-05-12T14:30:00Z   # restore specific timestamp
#
# Required environment variables (same as backup-postgres.sh):
#   POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_DB, PGPASSWORD
#   BACKUP_S3_BUCKET, BACKUP_S3_PREFIX, AWS_DEFAULT_REGION
#
# RTO target: 4 hours from incident declaration to verified restore.
# RPO target: 24 hours (daily backup cadence).
#
# Recovery tested: last quarterly drill TBD — update this line after each drill.
# Last restore drill: NOT YET EXECUTED — schedule before 2026-06-30.
#
# Exit codes:
#   0 — restore succeeded + health checks passed
#   1 — S3 download/verification failed
#   2 — pg_restore failed
#   3 — post-restore health checks failed
# =============================================================================
set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
BACKUP_TIMESTAMP="${1:-latest}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET required}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_DEFAULT_REGION

POSTGRES_HOST="${POSTGRES_HOST:?POSTGRES_HOST required}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:?POSTGRES_USER required}"
POSTGRES_DB="${POSTGRES_DB:?POSTGRES_DB required}"
export PGPASSWORD="${PGPASSWORD:?PGPASSWORD required}"

RESTORE_DIR="${RESTORE_DIR:-/tmp/pg_restore_$(date +%Y%m%d_%H%M%S)}"
mkdir -p "$RESTORE_DIR"
cd "$RESTORE_DIR"

_psql() { psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$@"; }

# ── 1. Resolve backup timestamp ──────────────────────────────────────────────
echo "== Resolving backup timestamp: $BACKUP_TIMESTAMP"
if [ "$BACKUP_TIMESTAMP" = "latest" ]; then
    BACKUP_TIMESTAMP=$(aws s3 ls "s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/" \
        | grep 'PRE ' | awk '{print $2}' | sed 's|/||' | sort | tail -1)
    if [ -z "$BACKUP_TIMESTAMP" ]; then
        echo "ERROR: No backups found in s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/" >&2
        exit 1
    fi
fi
echo "   Using backup: $BACKUP_TIMESTAMP"

# ── 2. Download backup + manifest ────────────────────────────────────────────
S3_PATH="s3://${BACKUP_S3_BUCKET}/${BACKUP_S3_PREFIX}/${BACKUP_TIMESTAMP}"
echo "== Downloading backup from $S3_PATH ..."
aws s3 cp "${S3_PATH}/backup.sql.gz" ./backup.sql.gz
aws s3 cp "${S3_PATH}/backup.sql.gz.sha256" ./backup.sql.gz.sha256

# ── 3. SHA-256 verification ──────────────────────────────────────────────────
echo "== Verifying SHA-256 manifest ..."
EXPECTED=$(cat backup.sql.gz.sha256 | awk '{print $1}')
ACTUAL=$(sha256sum backup.sql.gz | awk '{print $1}')
if [ "$EXPECTED" != "$ACTUAL" ]; then
    echo "ERROR: SHA-256 mismatch!" >&2
    echo "   Expected: $EXPECTED" >&2
    echo "   Actual:   $ACTUAL" >&2
    exit 1
fi
echo "   SHA-256 OK"

# ── 4. Terminate connections + recreate database ─────────────────────────────
echo "== Terminating connections to $POSTGRES_DB ..."
_psql -d postgres -c "
    SELECT pg_terminate_backend(pid)
    FROM pg_stat_activity
    WHERE datname = '$POSTGRES_DB' AND pid <> pg_backend_pid()
" 2>/dev/null || true

echo "== Dropping and recreating $POSTGRES_DB ..."
_psql -d postgres -c "DROP DATABASE IF EXISTS $POSTGRES_DB" 2>/dev/null || true
_psql -d postgres -c "CREATE DATABASE $POSTGRES_DB ENCODING 'UTF8'"

# ── 5. pg_restore ────────────────────────────────────────────────────────────
echo "== Restoring $POSTGRES_DB from backup ..."
gunzip -c backup.sql.gz | _psql -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 || {
    echo "ERROR: pg_restore failed." >&2
    exit 2
}

# ── 6. Post-restore health checks ────────────────────────────────────────────
echo "== Running post-restore health checks ..."

# Critical tables must have > 0 rows (confirm restore wasn't empty).
CRITICAL_TABLES=("tenants" "users" "django_migrations" "assets_asset")
HEALTH_FAIL=0
for table in "${CRITICAL_TABLES[@]}"; do
    count=$(_psql -d "$POSTGRES_DB" -tAc "SELECT COUNT(*) FROM $table" 2>/dev/null || echo 0)
    echo "   $table: $count rows"
    if [ "${count:-0}" -eq 0 ]; then
        echo "   WARNING: $table is empty — restore may be incomplete."
        HEALTH_FAIL=1
    fi
done

if [ "$HEALTH_FAIL" -ne 0 ]; then
    echo "ERROR: Post-restore health checks failed." >&2
    exit 3
fi

# ── 7. Run migrations to ensure schema is current ────────────────────────────
echo "== Running Django migrations ..."
if command -v python3 &>/dev/null && [ -f hub/manage.py ]; then
    python3 hub/manage.py migrate --noinput 2>&1 || {
        echo "WARNING: migrate failed — schema may be behind current code." >&2
        echo "   Run 'python3 hub/manage.py migrate --noinput' manually after restore." >&2
    }
else
    echo "   manage.py not available in this context — skip migrate."
    echo "   Run 'python3 hub/manage.py migrate --noinput' after restore."
fi

# ── Cleanup ──────────────────────────────────────────────────────────────────
echo "== Restore complete. Temp files at $RESTORE_DIR"
echo "   RTO clock stopped at $(date -u +%Y-%m-%dT%H:%M:%SZ)"
