#!/usr/bin/env bash
# =============================================================================
# scripts/tests/test_dr_restore_drill.sh
#
# TDD contract suite for scripts/dr/dr_restore_drill.sh — the pilot-readiness
# 4.4 REAL DR restore drill (backup → restore → row-count parity → drill
# report). Validates the --dry-run contract:
#   1. backup runs pg_dump in CUSTOM format against the postgres service
#   2. backup writes a SHA-256 manifest alongside the dump
#   3. restore-drill verifies the manifest BEFORE touching the dump
#   4. restore-drill creates a SCRATCH database (never the live one)
#   5. restore-drill restores with --clean --if-exists --no-owner
#   6. restore-drill runs row-count parity live vs scratch per probe table
#   7. restore-drill drops the scratch database afterwards
#   8. restore-drill emits the drill report JSON (RTO + parity results)
#   9. the drill report lands under docs/operations/dr-drill-reports/YYYY-MM/
#  10. backup sweeps dumps older than the retention window
#  11. flags (--compose-file/--env-file/--parity-tables/--label) propagate
#  12. unknown arguments are rejected
#
# Usage: bash scripts/tests/test_dr_restore_drill.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRILL_SCRIPT="${SCRIPT_DIR}/../dr/dr_restore_drill.sh"

if [[ ! -f "${DRILL_SCRIPT}" ]]; then
  echo "FAILED: ${DRILL_SCRIPT} does not exist (write it first — TDD RED)"
  exit 1
fi

PASS=0
FAIL=0
TESTS=()

pass() { PASS=$((PASS + 1)); TESTS+=("PASS: $1"); }
fail() { FAIL=$((FAIL + 1)); TESTS+=("FAIL: $1 — $2"); }

assert_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if grep -qF -- "${needle}" <<< "${haystack}"; then
    pass "${desc}"
  else
    fail "${desc}" "'${needle}' not found in output"
  fi
}

assert_not_contains() {
  local desc="$1" haystack="$2" needle="$3"
  if grep -qF -- "${needle}" <<< "${haystack}"; then
    fail "${desc}" "'${needle}' should not be in output"
  else
    pass "${desc}"
  fi
}

assert_line_before() {
  local desc="$1" haystack="$2" first="$3" second="$4"
  local first_line second_line
  first_line="$(echo "${haystack}" | grep -nF -- "${first}" | head -1 | cut -d: -f1)"
  second_line="$(echo "${haystack}" | grep -nF -- "${second}" | head -1 | cut -d: -f1)"
  if [[ -n "${first_line}" && -n "${second_line}" && "${first_line}" -lt "${second_line}" ]]; then
    pass "${desc}"
  else
    fail "${desc}" "'${first}' (line ${first_line:-?}) should come before '${second}' (line ${second_line:-?})"
  fi
}

# assert_between DESC HAYSTACK BEFORE MIDDLE AFTER — MIDDLE's line number must
# sit strictly between the FIRST occurrence of BEFORE and the LAST occurrence
# of AFTER (BEFORE and AFTER may appear multiple times).
assert_between() {
  local desc="$1" haystack="$2" before="$3" middle="$4" after="$5"
  local before_line middle_line after_line
  before_line="$(echo "${haystack}" | grep -nF -- "${before}" | head -1 | cut -d: -f1)"
  after_line="$(echo "${haystack}" | grep -nF -- "${after}" | tail -1 | cut -d: -f1)"
  middle_line="$(echo "${haystack}" | grep -nF -- "${middle}" | head -1 | cut -d: -f1)"
  if [[ -n "${before_line}" && -n "${middle_line}" && -n "${after_line}" \
        && "${before_line}" -lt "${middle_line}" && "${middle_line}" -lt "${after_line}" ]]; then
    pass "${desc}"
  else
    fail "${desc}" "'${middle}' (line ${middle_line:-?}) should sit between '${before}' (line ${before_line:-?}) and '${after}' (line ${after_line:-?})"
  fi
}

# A failing dry-run is a FAIL, not a silent suite death (`set -e` kills the
# script inside a bare VAR="$(...)" assignment — see assert_line_before's
# history in the post-deploy suite).
capture() {
  local name="$1"; shift
  local output
  if output="$(bash "${DRILL_SCRIPT}" "$@" 2>&1)"; then
    printf -v "${name}" '%s' "${output}"
    return 0
  fi
  fail "${name} dry-run exits 0" "dry-run '$*' exited non-zero: ${output}"
  printf -v "${name}" '%s' "${output}"
  return 1
}

BACKUP_OUT=""
capture BACKUP_OUT --dry-run backup || true

# 1-2. Dump + manifest
assert_contains "backup runs pg_dump in custom format" "${BACKUP_OUT}" "--format=custom"
assert_contains "backup targets the postgres service" "${BACKUP_OUT}" "postgres"
assert_contains "backup writes a SHA-256 manifest" "${BACKUP_OUT}" "sha256sum"
assert_contains "manifest saved alongside the dump" "${BACKUP_OUT}" ".sha256"

# 10. Retention sweep
assert_contains "backup sweeps dumps past the retention window" "${BACKUP_OUT}" "retention sweep"

RESTORE_OUT=""
capture RESTORE_OUT --dry-run restore-drill || true

# 3. Manifest gate before restore
assert_line_before "manifest verified before restore" "${RESTORE_OUT}" "manifest" "pg_restore"

# 4-5. Scratch DB + restore flags
assert_contains "restore drills into a SCRATCH database" "${RESTORE_OUT}" "_restore_drill"
assert_contains "scratch DB is dropped-if-exists then created" "${RESTORE_OUT}" "DROP DATABASE"
assert_contains "restore uses --clean --if-exists --no-owner" "${RESTORE_OUT}" "--clean --if-exists --no-owner"

# 6. Row-count parity
assert_contains "restore runs row-count parity" "${RESTORE_OUT}" "parity"
assert_contains "parity probes the tenants table" "${RESTORE_OUT}" "tenants"
assert_contains "parity probes the users table" "${RESTORE_OUT}" "users"
assert_contains "parity probes the audit_events table" "${RESTORE_OUT}" "audit_events"

# 7. Scratch drop after parity (DROP appears twice: drop-if-exists at create
#    time and the final cleanup — parity must sit between them).
assert_between "parity runs after scratch create, before the final drop" \
  "${RESTORE_OUT}" "CREATE DATABASE" "parity:" "DROP DATABASE"

# 8-9. Drill report
assert_contains "restore emits the drill report JSON" "${RESTORE_OUT}" "drill-report"
assert_contains "report lands under docs/operations/dr-drill-reports" "${RESTORE_OUT}" "docs/operations/dr-drill-reports"
assert_contains "report records the achieved RTO" "${RESTORE_OUT}" "rto_seconds"
assert_contains "report records the snapshot/dump filename" "${RESTORE_OUT}" "backup_file"

# 11. Flag propagation
FLAG_OUT=""
capture FLAG_OUT --dry-run --compose-file docker-compose.staging.yml \
  --env-file .env.staging --project-name hub-staging \
  --parity-tables "tenants users" --label "4.4 rehearsal" restore-drill || true
assert_contains "custom compose file propagates" "${FLAG_OUT}" "docker-compose.staging.yml"
assert_contains "custom env file propagates" "${FLAG_OUT}" ".env.staging"
assert_contains "project name propagates" "${FLAG_OUT}" "hub-staging"
assert_contains "custom parity tables propagate (tenants)" "${FLAG_OUT}" "FROM tenants"
assert_contains "custom parity tables propagate (users)" "${FLAG_OUT}" "FROM users"
assert_not_contains "default parity tables overridden away" "${FLAG_OUT}" "FROM audit_events"
assert_contains "drill label propagates to the report" "${FLAG_OUT}" "4.4 rehearsal"

# 12. Unknown args rejected
if bash "${DRILL_SCRIPT}" --dry-run --bogus-flag backup >/dev/null 2>&1; then
  fail "unknown arguments rejected" "exit 0 with --bogus-flag"
else
  pass "unknown arguments rejected"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " test_dr_restore_drill.sh — ${PASS} passed / ${FAIL} failed"
echo "════════════════════════════════════════════════════════════"
for t in "${TESTS[@]}"; do echo "  $t"; done
[[ "${FAIL}" -eq 0 ]]
