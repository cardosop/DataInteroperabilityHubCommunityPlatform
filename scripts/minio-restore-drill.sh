#!/usr/bin/env bash
# =============================================================================
# minio-restore-drill.sh — REAL MinIO backup/restore drill (W8.2).
#
# Exercises the actual loss-recovery mechanism against the live test-stack
# MinIO, isolated in a dedicated drill bucket.  The drill body runs INSIDE
# the minio container (where the mc client + sha256sum live — the same
# binaries the image's own healthcheck uses):
#
#   1. create a drill bucket with N known payloads (sha256 recorded)
#   2. mirror-out the bucket to a backup directory (the "backup")
#   3. DELETE the bucket objects (the simulated data loss)
#   4. mirror-back from the backup directory (the "restore")
#   5. sha256-verify every restored object against the recorded digests
#   6. report the restore wall-clock time against the RTO target (2h)
#   7. clean up (drill bucket + in-container backup dir)
#
# Credentials: mc's local alias is pre-configured by the container
# healthcheck env; nothing is printed.
#
# Usage:  scripts/minio-restore-drill.sh [bucket-name]
#   MINIO_CONTAINER — container name (default: hub-test-minio)
#   MINIO_DRILL_PAYLOADS — number of payload objects (default: 7)
#   MINIO_DRILL_RTO_SECONDS — RTO target (default: 7200 = 2h)
#
# Exit codes:
#   0 — drill passed (restore verified within RTO)
#   1 — setup/credential failure
#   2 — mirror-out (backup) failure
#   3 — mirror-back (restore) failure
#   4 — integrity verification failure
#   5 — RTO exceeded
# =============================================================================
set -euo pipefail

MINIO_CONTAINER="${MINIO_CONTAINER:-hub-test-minio}"
DRILL_BUCKET="${1:-w82-drill-$(date +%Y%m%d%H%M%S)}"
PAYLOAD_COUNT="${MINIO_DRILL_PAYLOADS:-7}"
RTO_SECONDS="${MINIO_DRILL_RTO_SECONDS:-7200}"

log() { echo "[$(date -u +%H:%M:%S)] $*"; }

if ! docker ps --format '{{.Names}}' | grep -qx "$MINIO_CONTAINER"; then
    log "ERROR: minio container '${MINIO_CONTAINER}' is not running" >&2
    exit 1
fi

log "Drill bucket: ${DRILL_BUCKET} (${PAYLOAD_COUNT} payloads, RTO ${RTO_SECONDS}s)"

# The drill body runs INSIDE the container: mc's local alias, payload
# files, backup dir, and sha256sum all live there.  The host only relays
# stdout/stderr and the exit code (docker exec propagates it).
docker exec -i "$MINIO_CONTAINER" sh -s -- "$DRILL_BUCKET" "$PAYLOAD_COUNT" "$RTO_SECONDS" <<'DRILL'
set -euo pipefail
BUCKET="$1"; COUNT="$2"; RTO="$3"
BASE="/tmp/w82-drill"
PAYLOADS="$BASE/payloads"; BACKUP="$BASE/backup"; MANIFEST="$BASE/expected.sha256"
rm -rf "$BASE"; mkdir -p "$PAYLOADS" "$BACKUP"

log() { echo "[drill] $*"; }

# ── 1. Drill bucket + known payloads ──────────────────────────────────────
log "Creating bucket ${BUCKET} with ${COUNT} payloads..."
mc mb --ignore-existing "local/${BUCKET}" >/dev/null 2>&1 || { log "ERROR: bucket create failed" >&2; exit 1; }
: > "$MANIFEST"
i=1
while [ "$i" -le "$COUNT" ]; do
    payload="$PAYLOADS/object-${i}.bin"
    head -c $((1024 * i + 37)) /dev/urandom > "$payload"
    digest="$(set -- $(sha256sum "$payload"); echo "$1")"
    printf '%s  object-%s.bin\n' "$digest" "$i" >> "$MANIFEST"
    mc cp --quiet "$payload" "local/${BUCKET}/object-${i}.bin" || { log "ERROR: upload failed" >&2; exit 1; }
    i=$((i + 1))
done
log "Uploaded ${COUNT} payloads; expected digests recorded."

# ── 2. Mirror-out (the backup) ────────────────────────────────────────────
log "Mirroring bucket -> backup dir (${BACKUP})..."
mc mirror --quiet "local/${BUCKET}" "$BACKUP" || { log "ERROR: mirror-out failed" >&2; exit 2; }
log "Backup holds $(find "$BACKUP" -type f | wc -l) files."

# ── 3. Simulated loss ─────────────────────────────────────────────────────
log "Simulating data loss: deleting all bucket objects..."
mc rm --recursive --force "local/${BUCKET}" >/dev/null || { log "ERROR: delete failed" >&2; exit 2; }
log "Objects remaining after loss: $(mc ls --recursive "local/${BUCKET}" 2>/dev/null | wc -l)."

# ── 4. Mirror-back (the restore) ──────────────────────────────────────────
log "Restoring from backup..."
STARTED="$(date -u +%s)"
mc mirror --quiet "$BACKUP" "local/${BUCKET}" || { log "ERROR: mirror-back failed" >&2; exit 3; }
FINISHED="$(date -u +%s)"

# ── 5. Verify every restored object ───────────────────────────────────────
log "Verifying restored objects against the recorded digests..."
FAILED=0
while read -r expected name; do
    if ! mc cat "local/${BUCKET}/${name}" > "$PAYLOADS/restored-${name}" 2>/dev/null; then
        log "ERROR: restored object missing: ${name}" >&2
        FAILED=1
        continue
    fi
    actual="$(set -- $(sha256sum "$PAYLOADS/restored-${name}"); echo "$1")"
    if [ "$actual" != "$expected" ]; then
        log "ERROR: digest mismatch for ${name}" >&2
        FAILED=1
    fi
done < "$MANIFEST"
if [ "$FAILED" -ne 0 ]; then
    log "INTEGRITY FAILURE" >&2
    exit 4
fi
log "All ${COUNT} restored objects verified (SHA-256 OK)."

# ── 6. RTO report + cleanup ───────────────────────────────────────────────
ELAPSED=$((FINISHED - STARTED))
log "Restore wall-clock: ${ELAPSED}s (RTO target: ${RTO}s)"
rm -rf "$BASE"
mc rm --recursive --force "local/${BUCKET}" >/dev/null 2>&1 || true
if [ "$ELAPSED" -gt "$RTO" ]; then
    log "RTO EXCEEDED" >&2
    exit 5
fi
log "MINIO RESTORE DRILL PASSED — ${COUNT}/${COUNT} objects restored and verified in ${ELAPSED}s."
exit 0
DRILL

log "Drill finished (exit $?)."
