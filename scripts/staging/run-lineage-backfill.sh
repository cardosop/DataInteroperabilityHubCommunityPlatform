#!/usr/bin/env bash
#
# Phase 228 (228.0.DoD.3) — operator wrapper for the staging lineage
# backfill. Bundles the full procedure the runbook describes:
#
#   1. Pre-snapshot the open-edge count + JSON-entry count for the
#      target scope (per tenant or whole-DB) so the operator has a
#      verifiable "before" number.
#   2. Run ``backfill_lineage_edges`` with the canonical staging flags
#      (``--resume-key=lineage-backfill-staging-$DATE``).
#   3. Run ``lineage_drift_check`` post-backfill — exit-code-meaningful
#      so this script's exit code matches the verification result.
#   4. Archive every step's stdout to a dated artefact directory so the
#      run is auditable after the fact (CI uploads as workflow artefact).
#
# Engineering invariants
# ----------------------
# - All steps run inside ``set -euo pipefail`` so a missed prerequisite
#   surfaces immediately; nothing is silently skipped.
# - The backfill is idempotent (REQ-LIN-003), so a re-run after a
#   transient failure converges the state without operator intervention.
# - The drift-check is read-only, so safe to run during business hours.
# - Output paths default to ``audit-reports/lineage-backfill/<DATE>/``;
#   override via ``LINEAGE_AUDIT_DIR`` env if running outside the
#   canonical staging-pod working directory.
#
# Usage::
#
#     # Whole-DB run (default, used by the post-deploy CI workflow):
#     ./scripts/staging/run-lineage-backfill.sh
#
#     # Per-tenant run (operator escalation):
#     TENANT=<uuid> ./scripts/staging/run-lineage-backfill.sh
#
#     # Override the artefact dir (CI):
#     LINEAGE_AUDIT_DIR=/tmp/lineage-artefact ./scripts/staging/run-lineage-backfill.sh
#
# Exit codes::
#
#     0 — backfill ran cleanly + drift ≤ tolerance.
#     1 — drift > tolerance after backfill (page on-call per runbook).
#     >1 — backfill or pre-snapshot itself failed (Django / DB error).

set -euo pipefail

# ---- Resolve manage.py ------------------------------------------------------

MANAGE_PY=""
for candidate in \
    /app/hub/manage.py \
    /workspace/hub/manage.py \
    "$(pwd)/hub/manage.py" \
    "$(pwd)/manage.py"; do
    if [[ -f "$candidate" ]]; then
        MANAGE_PY="$candidate"
        break
    fi
done
if [[ -z "$MANAGE_PY" ]]; then
    echo "ERROR: cannot locate manage.py — set HUB_MANAGE_PY or run from repo root" >&2
    exit 2
fi

# ---- Configuration ----------------------------------------------------------

DATE_STAMP="${DATE_STAMP:-$(date -u +%Y-%m-%d)}"
LINEAGE_AUDIT_DIR="${LINEAGE_AUDIT_DIR:-audit-reports/lineage-backfill/${DATE_STAMP}}"
TENANT="${TENANT:-}"
TOLERANCE="${LINEAGE_TOLERANCE:-0.001}"  # default 0.1% per REQ-LIN-003
RESUME_KEY="${RESUME_KEY:-lineage-backfill-staging-${DATE_STAMP}}"

mkdir -p "${LINEAGE_AUDIT_DIR}"

PRE_SNAPSHOT_FILE="${LINEAGE_AUDIT_DIR}/01-pre-snapshot.json"
BACKFILL_LOG_FILE="${LINEAGE_AUDIT_DIR}/02-backfill.log"
POST_DRIFT_FILE="${LINEAGE_AUDIT_DIR}/03-drift-check.json"
SUMMARY_FILE="${LINEAGE_AUDIT_DIR}/00-summary.json"

TENANT_FLAG=""
if [[ -n "$TENANT" ]]; then
    TENANT_FLAG="--tenant=${TENANT}"
fi

echo "================================================================"
echo "Phase 228 — staging lineage-backfill operator wrapper"
echo "  Date stamp ........... ${DATE_STAMP}"
echo "  Resume key ........... ${RESUME_KEY}"
echo "  Tenant scope ......... ${TENANT:-<all tenants>}"
echo "  Tolerance ............ ${TOLERANCE}"
echo "  Artefact dir ......... ${LINEAGE_AUDIT_DIR}"
echo "================================================================"

# ---- Step 1 — pre-snapshot --------------------------------------------------

echo "[1/3] Pre-snapshot (drift baseline before backfill)…"
# A pre-backfill drift check shows the drift-state we're about to fix.
# We record but don't fail on this step (DRIFT here is exactly what
# we're about to correct).
set +e
python3 "${MANAGE_PY}" lineage_drift_check ${TENANT_FLAG} --tolerance="${TOLERANCE}" \
    > "${PRE_SNAPSHOT_FILE}" 2>&1
PRE_RC=$?
set -e

# Report-or-error: on transient failure (DB connection, missing table)
# the JSON file will be empty; surface that explicitly.
if [[ ! -s "${PRE_SNAPSHOT_FILE}" ]]; then
    echo "ERROR: pre-snapshot produced no output (rc=${PRE_RC}). Check Django + DB."
    cat "${PRE_SNAPSHOT_FILE}" >&2 || true
    exit 2
fi
echo "  pre-snapshot: $(grep -E '"status"' "${PRE_SNAPSHOT_FILE}" | head -1)"

# ---- Step 2 — apply the backfill --------------------------------------------

echo "[2/3] Running backfill (idempotent, resumable via key=${RESUME_KEY})…"
python3 "${MANAGE_PY}" backfill_lineage_edges \
    ${TENANT_FLAG} \
    --resume-key="${RESUME_KEY}" \
    --verify-tolerance="${TOLERANCE}" \
    > "${BACKFILL_LOG_FILE}" 2>&1
echo "  backfill log: ${BACKFILL_LOG_FILE}"
tail -3 "${BACKFILL_LOG_FILE}" || true

# ---- Step 3 — post-backfill verification ------------------------------------

echo "[3/3] Post-backfill drift-check…"
set +e
python3 "${MANAGE_PY}" lineage_drift_check ${TENANT_FLAG} --tolerance="${TOLERANCE}" \
    > "${POST_DRIFT_FILE}" 2>&1
DRIFT_RC=$?
set -e

if [[ ! -s "${POST_DRIFT_FILE}" ]]; then
    echo "ERROR: post-backfill drift-check produced no output (rc=${DRIFT_RC})."
    cat "${POST_DRIFT_FILE}" >&2 || true
    exit 2
fi

POST_STATUS=$(grep -oE '"status":\s*"[^"]+"' "${POST_DRIFT_FILE}" | head -1 || echo '"status":"UNKNOWN"')
echo "  post-status: ${POST_STATUS}"

# ---- Summary artefact --------------------------------------------------------

cat > "${SUMMARY_FILE}" <<EOF
{
  "phase": "228.0.DoD.3",
  "date_stamp": "${DATE_STAMP}",
  "resume_key": "${RESUME_KEY}",
  "tenant": "${TENANT:-null}",
  "tolerance": "${TOLERANCE}",
  "pre_snapshot_file": "01-pre-snapshot.json",
  "backfill_log_file": "02-backfill.log",
  "post_drift_file": "03-drift-check.json",
  "post_status_token": ${POST_STATUS#*:},
  "drift_check_exit_code": ${DRIFT_RC},
  "operator_runbook": "docs/runbooks/lineage-edge-backfill-failure.md"
}
EOF
echo "Summary archived to ${SUMMARY_FILE}"

# ---- Exit-code-meaningful ----------------------------------------------------

if [[ "${DRIFT_RC}" -ne 0 ]]; then
    echo
    echo "FAIL: post-backfill drift-check exited ${DRIFT_RC} (DRIFT > tolerance)."
    echo "Page on-call per docs/runbooks/lineage-edge-sync-drift.md."
    exit "${DRIFT_RC}"
fi

echo
echo "OK: backfill ran cleanly + drift ≤ ${TOLERANCE}. DoD.3 satisfied for this scope."
exit 0
