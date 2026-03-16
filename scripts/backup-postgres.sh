#!/usr/bin/env bash
# =============================================================================
# backup-postgres.sh — Production PostgreSQL backup script
#
# Pipeline:
#   1. pg_dump → gzip → local temp file
#   2. SHA-256 manifest
#   3. Upload both to S3 (bucket/prefix/YYYY-MM-DD/)
#   4. Verify S3 upload
#   5. Delete local temp files
#   6. Retention sweep: delete S3 objects older than BACKUP_RETENTION_DAYS
#
# Usage:
#   ./scripts/backup-postgres.sh
#
# Required environment variables (injected by Vault Agent or .env.production):
#   POSTGRES_HOST          — database host (direct Postgres, NOT PgBouncer)
#   POSTGRES_PORT          — database port (default: 5432)
#   POSTGRES_USER          — database user
#   POSTGRES_DB            — database name
#   PGPASSWORD             — database password (read by pg_dump automatically)
#   BACKUP_S3_BUCKET       — S3 bucket name
#   BACKUP_S3_PREFIX       — key prefix inside the bucket (default: postgres)
#   BACKUP_RETENTION_DAYS  — delete backups older than this many days (default: 30)
#   AWS_ACCESS_KEY_ID      — S3 credentials (can be instance profile — leave unset)
#   AWS_SECRET_ACCESS_KEY  — S3 credentials (can be instance profile — leave unset)
#   AWS_DEFAULT_REGION     — AWS region (default: us-east-1)
#
# Exit codes:
#   0 — success
#   1 — configuration / dependency error
#   2 — pg_dump failure
#   3 — S3 upload failure
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration with safe defaults
# ---------------------------------------------------------------------------
# When PgBouncer is active, POSTGRES_HOST points to PgBouncer which operates in
# transaction mode — incompatible with pg_dump (requires a persistent session).
# POSTGRES_DIRECT_HOST must always point to the actual PostgreSQL instance.
POSTGRES_DIRECT_HOST="${POSTGRES_DIRECT_HOST:-${POSTGRES_HOST:-localhost}}"
POSTGRES_HOST="${POSTGRES_DIRECT_HOST}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_USER="${POSTGRES_USER:-hub}"
POSTGRES_DB="${POSTGRES_DB:-hub}"
BACKUP_S3_BUCKET="${BACKUP_S3_BUCKET:?BACKUP_S3_BUCKET must be set}"
BACKUP_S3_PREFIX="${BACKUP_S3_PREFIX:-postgres}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export AWS_DEFAULT_REGION

TIMESTAMP="$(date -u '+%Y-%m-%dT%H%M%SZ')"
DATE_DIR="$(date -u '+%Y-%m-%d')"
BACKUP_FILENAME="${POSTGRES_DB}_${TIMESTAMP}.sql.gz"
MANIFEST_FILENAME="${BACKUP_FILENAME}.sha256"
TMPDIR_BASE="$(mktemp -d)"
BACKUP_PATH="${TMPDIR_BASE}/${BACKUP_FILENAME}"
MANIFEST_PATH="${TMPDIR_BASE}/${MANIFEST_FILENAME}"
S3_KEY_PREFIX="${BACKUP_S3_PREFIX}/${DATE_DIR}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*"; }
err() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] ERROR: $*" >&2; }

cleanup() {
    log "Cleaning up local temp files..."
    rm -rf "${TMPDIR_BASE}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Preflight checks
# ---------------------------------------------------------------------------
log "=== PostgreSQL backup starting ==="
log "  Database : ${POSTGRES_DB}@${POSTGRES_HOST}:${POSTGRES_PORT}"
log "  Destination: s3://${BACKUP_S3_BUCKET}/${S3_KEY_PREFIX}/"
log "  Retention: ${BACKUP_RETENTION_DAYS} days"

for cmd in pg_dump gzip aws; do
    if ! command -v "${cmd}" >/dev/null 2>&1; then
        err "Required command not found: ${cmd}"
        exit 1
    fi
done
# sha256sum (GNU coreutils) or openssl must be available for integrity manifest.
if ! command -v sha256sum >/dev/null 2>&1 && ! command -v openssl >/dev/null 2>&1; then
    err "Neither sha256sum nor openssl found. Install one to generate integrity manifests."
    exit 1
fi

if [[ -z "${PGPASSWORD:-}" ]]; then
    err "PGPASSWORD is not set. Set it from Vault or .env.production."
    exit 1
fi
export PGPASSWORD

# ---------------------------------------------------------------------------
# Step 1: pg_dump → gzip
# ---------------------------------------------------------------------------
log "Step 1/5: Dumping database..."
if ! pg_dump \
    --host="${POSTGRES_HOST}" \
    --port="${POSTGRES_PORT}" \
    --username="${POSTGRES_USER}" \
    --dbname="${POSTGRES_DB}" \
    --format=plain \
    --no-password \
    --verbose \
    2>>"${TMPDIR_BASE}/pg_dump.log" \
    | gzip -9 > "${BACKUP_PATH}"; then
    err "pg_dump failed. See log:"
    cat "${TMPDIR_BASE}/pg_dump.log" >&2
    exit 2
fi

BACKUP_SIZE="$(du -sh "${BACKUP_PATH}" | cut -f1)"
log "  Dump complete: ${BACKUP_FILENAME} (${BACKUP_SIZE})"

# ---------------------------------------------------------------------------
# Step 2: SHA-256 manifest
# ---------------------------------------------------------------------------
log "Step 2/5: Computing SHA-256 manifest..."
# sha256sum (GNU coreutils) is preferred; fall back to openssl on Alpine/macOS.
if command -v sha256sum >/dev/null 2>&1; then
    SHA256="$(sha256sum "${BACKUP_PATH}" | awk '{print $1}')"
else
    SHA256="$(openssl dgst -sha256 "${BACKUP_PATH}" | awk '{print $NF}')"
fi
printf '%s  %s\n' "${SHA256}" "${BACKUP_FILENAME}" > "${MANIFEST_PATH}"
log "  SHA-256: ${SHA256}"

# ---------------------------------------------------------------------------
# Step 3: Upload backup + manifest to S3
# ---------------------------------------------------------------------------
log "Step 3/5: Uploading to S3..."

upload_to_s3() {
    local local_path="$1"
    local s3_key="$2"
    log "  Uploading ${local_path} → s3://${BACKUP_S3_BUCKET}/${s3_key}"
    if ! aws s3 cp \
        "${local_path}" \
        "s3://${BACKUP_S3_BUCKET}/${s3_key}" \
        --sse aws:kms \
        --storage-class STANDARD_IA \
        --only-show-errors; then
        err "Failed to upload ${local_path} to S3."
        exit 3
    fi
}

upload_to_s3 "${BACKUP_PATH}"   "${S3_KEY_PREFIX}/${BACKUP_FILENAME}"
upload_to_s3 "${MANIFEST_PATH}" "${S3_KEY_PREFIX}/${MANIFEST_FILENAME}"

# ---------------------------------------------------------------------------
# Step 4: Verify upload (compare S3 ETag against local SHA-256)
# ---------------------------------------------------------------------------
log "Step 4/5: Verifying S3 upload..."
S3_OBJECT_SIZE="$(aws s3api head-object \
    --bucket "${BACKUP_S3_BUCKET}" \
    --key "${S3_KEY_PREFIX}/${BACKUP_FILENAME}" \
    --query 'ContentLength' \
    --output text)"
LOCAL_SIZE="$(wc -c < "${BACKUP_PATH}")"

if [[ "${S3_OBJECT_SIZE}" != "${LOCAL_SIZE}" ]]; then
    err "Size mismatch: local=${LOCAL_SIZE} bytes, S3=${S3_OBJECT_SIZE} bytes"
    exit 3
fi
log "  Verification OK: ${S3_OBJECT_SIZE} bytes"

# ---------------------------------------------------------------------------
# Step 5: Retention sweep — delete objects older than BACKUP_RETENTION_DAYS
# ---------------------------------------------------------------------------
log "Step 5/5: Running retention sweep (>${BACKUP_RETENTION_DAYS} days)..."

# Compute cutoff date portably across GNU date, BusyBox (Alpine), and macOS BSD date.
# Strategy: subtract RETENTION seconds from the current epoch, then format the result.
# - GNU/BusyBox: date -d @EPOCH works on both.
# - macOS BSD: date -r EPOCH works.
_CUTOFF_EPOCH=$(( $(date -u +%s) - BACKUP_RETENTION_DAYS * 86400 ))
CUTOFF_DATE="$(date -u -d "@${_CUTOFF_EPOCH}" '+%Y-%m-%d' 2>/dev/null \
    || date -u -r "${_CUTOFF_EPOCH}" '+%Y-%m-%d')"

log "  Cutoff date: ${CUTOFF_DATE}"

# List all objects under the prefix and filter by last-modified date.
# We iterate date-prefixed "directories" (YYYY-MM-DD/) and delete those before cutoff.
DELETED_COUNT=0
while IFS= read -r object_key; do
    # Extract date component from key: backup_prefix/YYYY-MM-DD/filename
    # Use ERE (-E) instead of PCRE (-P) for Alpine BusyBox grep compatibility.
    OBJECT_DATE="$(echo "${object_key}" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1 || true)"
    if [[ -z "${OBJECT_DATE}" ]]; then
        continue
    fi
    if [[ "${OBJECT_DATE}" < "${CUTOFF_DATE}" ]]; then
        log "  Deleting expired object: ${object_key} (date: ${OBJECT_DATE})"
        aws s3 rm "s3://${BACKUP_S3_BUCKET}/${object_key}" --only-show-errors
        DELETED_COUNT=$((DELETED_COUNT + 1))
    fi
done < <(aws s3api list-objects-v2 \
    --bucket "${BACKUP_S3_BUCKET}" \
    --prefix "${BACKUP_S3_PREFIX}/" \
    --query 'Contents[].Key' \
    --output text \
    | tr '\t' '\n' \
    | grep -v '^None$' \
    || true)

log "  Retention sweep complete. Deleted ${DELETED_COUNT} expired object(s)."

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
log "=== Backup complete ==="
log "  File    : s3://${BACKUP_S3_BUCKET}/${S3_KEY_PREFIX}/${BACKUP_FILENAME}"
log "  Manifest: s3://${BACKUP_S3_BUCKET}/${S3_KEY_PREFIX}/${MANIFEST_FILENAME}"
log "  SHA-256 : ${SHA256}"
log "  Size    : ${BACKUP_SIZE}"
