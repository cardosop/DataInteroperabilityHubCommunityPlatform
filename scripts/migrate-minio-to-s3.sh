#!/usr/bin/env bash
# migrate-minio-to-s3.sh — Stream objects from MinIO to AWS S3 (Phase 18.8)
#
# Usage:
#   MINIO_ALIAS=myminio \
#   MINIO_BUCKET=hub-assets \
#   S3_BUCKET=hub-assets-production \
#   AWS_REGION=us-east-1 \
#   ./scripts/migrate-minio-to-s3.sh [--dry-run]
#
# Flags:
#   --dry-run   List what would be migrated without uploading anything.
#               Prints the same JSONL format with status="dry-run" for each
#               object that would be uploaded and status="skipped" for objects
#               already present in S3.  No writes to S3 or LOG_FILE.
#
# Prerequisites:
#   - mc (MinIO client) configured: mc alias set $MINIO_ALIAS <url> <key> <secret>
#   - aws CLI configured with credentials (or IRSA if running in-cluster)
#   - jq installed
#
# The script is idempotent: it checks for an existing S3 object with a matching
# ETag (MD5) before uploading and skips objects that already exist.
#
# Progress is written as JSONL to $LOG_FILE (default: /tmp/minio-to-s3-migration.jsonl).
# Each line is one of:
#   {"status":"skipped","key":"<key>","reason":"already_exists"}
#   {"status":"ok","key":"<key>","etag":"<etag>","bytes":<n>}
#   {"status":"error","key":"<key>","error":"<message>"}
#   {"status":"dry-run","key":"<key>","bytes":<n>}   (--dry-run only)
#
# Re-running after a partial failure resumes from where it left off.

set -euo pipefail

# Parse flags
DRY_RUN=0
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY_RUN=1 ;;
        *) echo "ERROR: Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

MINIO_ALIAS="${MINIO_ALIAS:?Set MINIO_ALIAS}"
MINIO_BUCKET="${MINIO_BUCKET:?Set MINIO_BUCKET}"
S3_BUCKET="${S3_BUCKET:?Set S3_BUCKET}"
AWS_REGION="${AWS_REGION:-us-east-1}"
LOG_FILE="${LOG_FILE:-/tmp/minio-to-s3-migration.jsonl}"
CONCURRENCY="${CONCURRENCY:-4}"  # parallel uploads

log() {
    echo "$*" | tee -a "$LOG_FILE"
}

log_json() {
    echo "$1" | tee -a "$LOG_FILE"
}

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "=== DRY-RUN: MinIO → S3 migration preview $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >&2
else
    echo "=== MinIO → S3 migration started $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >&2
fi
echo "    Source : mc alias=$MINIO_ALIAS bucket=$MINIO_BUCKET" >&2
echo "    Dest   : s3://$S3_BUCKET ($AWS_REGION)" >&2
if [[ "$DRY_RUN" -eq 0 ]]; then
    echo "    Log    : $LOG_FILE" >&2
fi

# Verify tools are available
for tool in mc aws jq; do
    if ! command -v "$tool" &>/dev/null; then
        echo "ERROR: '$tool' not found in PATH" >&2
        exit 1
    fi
done

# Verify MinIO alias is reachable
if ! mc ls "${MINIO_ALIAS}/${MINIO_BUCKET}" &>/dev/null; then
    echo "ERROR: Cannot list mc://$MINIO_ALIAS/$MINIO_BUCKET — check alias config" >&2
    exit 1
fi

# Verify S3 bucket is reachable
if ! aws s3 ls "s3://${S3_BUCKET}" --region "$AWS_REGION" &>/dev/null; then
    echo "ERROR: Cannot list s3://$S3_BUCKET — check AWS credentials and bucket existence" >&2
    exit 1
fi

migrate_object() {
    local key="$1"

    # --- stat MinIO object once (reuse for etag, content-type, size) ---
    local minio_stat
    minio_stat=$(mc stat --json "${MINIO_ALIAS}/${MINIO_BUCKET}/${key}" 2>/dev/null || echo "{}")

    local minio_etag
    minio_etag=$(echo "$minio_stat" | jq -r '.etag // ""' | tr -d '"')

    local byte_count
    byte_count=$(echo "$minio_stat" | jq -r '.size // 0')

    # --- idempotency check: compare ETags ---
    local s3_etag
    s3_etag=$(aws s3api head-object \
        --bucket "$S3_BUCKET" \
        --key "$key" \
        --region "$AWS_REGION" \
        --query 'ETag' \
        --output text 2>/dev/null | tr -d '"' || echo "")

    if [[ -n "$s3_etag" && "$s3_etag" == "$minio_etag" ]]; then
        echo "{\"status\":\"skipped\",\"key\":\"${key}\",\"reason\":\"already_exists\"}"
        [[ "$DRY_RUN" -eq 0 ]] && log_json "{\"status\":\"skipped\",\"key\":\"${key}\",\"reason\":\"already_exists\"}"
        return 0
    fi

    # --- dry-run: report what would be uploaded ---
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "{\"status\":\"dry-run\",\"key\":\"${key}\",\"bytes\":${byte_count}}"
        return 0
    fi

    # --- stream: mc cat | aws s3 cp --stdin ---
    local content_type
    content_type=$(echo "$minio_stat" | jq -r '.metadata."Content-Type" // "application/octet-stream"')

    local upload_err
    if upload_err=$(mc cat "${MINIO_ALIAS}/${MINIO_BUCKET}/${key}" \
        | aws s3 cp - "s3://${S3_BUCKET}/${key}" \
            --region "$AWS_REGION" \
            --content-type "$content_type" \
            --expected-size "$byte_count" \
            --no-progress 2>&1); then

        local new_etag
        new_etag=$(aws s3api head-object \
            --bucket "$S3_BUCKET" \
            --key "$key" \
            --region "$AWS_REGION" \
            --query 'ETag' \
            --output text 2>/dev/null | tr -d '"' || echo "")

        log_json "{\"status\":\"ok\",\"key\":\"${key}\",\"etag\":\"${new_etag}\",\"bytes\":${byte_count}}"
    else
        local escaped_err
        escaped_err=$(echo "$upload_err" | jq -Rs '.')
        log_json "{\"status\":\"error\",\"key\":\"${key}\",\"error\":${escaped_err}}"
        return 1
    fi
}

export -f migrate_object log_json
export MINIO_ALIAS MINIO_BUCKET S3_BUCKET AWS_REGION LOG_FILE DRY_RUN

# List all objects and run migrations in parallel via xargs
# In dry-run mode output goes to stdout only (no LOG_FILE writes).
mc ls --recursive --json "${MINIO_ALIAS}/${MINIO_BUCKET}" \
    | jq -r '.key' \
    | xargs -P "$CONCURRENCY" -I{} bash -c 'migrate_object "$@"' _ {}

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "" >&2
    echo "=== DRY-RUN complete — no objects were uploaded ===" >&2
    exit 0
fi

# Summary (live run only)
TOTAL=$(wc -l < "$LOG_FILE" || echo 0)
OK=$(grep -c '"status":"ok"' "$LOG_FILE" || echo 0)
SKIPPED=$(grep -c '"status":"skipped"' "$LOG_FILE" || echo 0)
ERRORS=$(grep -c '"status":"error"' "$LOG_FILE" || echo 0)

echo "" >&2
echo "=== Migration complete $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" >&2
echo "    Total  : $TOTAL" >&2
echo "    OK     : $OK" >&2
echo "    Skipped: $SKIPPED" >&2
echo "    Errors : $ERRORS" >&2
echo "    Log    : $LOG_FILE" >&2

if [[ "$ERRORS" -gt 0 ]]; then
    echo "WARN: $ERRORS object(s) failed — re-run to retry (idempotent)" >&2
    exit 1
fi
