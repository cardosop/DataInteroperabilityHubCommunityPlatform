#!/usr/bin/env bash
# =============================================================================
# scripts/tests/test_restore_verify_rds.sh
#
# TDD contract suite for scripts/dr/restore_verify_rds.sh — the RDS-path DR
# drill. Pins the pilot-readiness 4.4 root-cause fix: the post-restore
# "health check" was an HTTP curl against the RDS ENDPOINT (a database, not
# an HTTP server — it could never pass); the verification is now a REAL
# database check (connectivity + row-count parity) with a `--verify-db` mode
# that runs against ANY Postgres URL (so the verification code path is
# exercised for real, today, against the local test stack).
#
#   1. dry-run discovers the latest automated snapshot (aws rds describe)
#   2. dry-run restores into a TEMP instance (never the source)
#   3. dry-run runs migrate against the temp instance
#   4. dry-run verifies via a DATABASE check — never an HTTP curl
#   5. dry-run emits the RTO JSON report (rto_seconds, rto_within_target)
#   6. dry-run tears the temp instance down
#   7. --verify-db runs connectivity + parity probes against a real Postgres
#   8. --verify-db fails non-zero when the database is unreachable
#   9. missing aws CLI is rejected with a clear error
#  10. unknown arguments are rejected
#
# Tests 1-6, 9, 10 run offline (dry-run). Tests 7-8 need a reachable Postgres
# (VERIFY_DB_URL env var; skipped with a named dependency when unset).
#
# Usage: bash scripts/tests/test_restore_verify_rds.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RDS_SCRIPT="${SCRIPT_DIR}/../dr/restore_verify_rds.sh"

if [[ ! -f "${RDS_SCRIPT}" ]]; then
  echo "FAILED: ${RDS_SCRIPT} does not exist (write it first — TDD RED)"
  exit 1
fi

PASS=0
FAIL=0
SKIP=0
TESTS=()

pass() { PASS=$((PASS + 1)); TESTS+=("PASS: $1"); }
fail() { FAIL=$((FAIL + 1)); TESTS+=("FAIL: $1 — $2"); }
skip() { SKIP=$((SKIP + 1)); TESTS+=("SKIP: $1 — $2"); }

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

capture() {
  local name="$1"; shift
  local output
  if output="$(bash "${RDS_SCRIPT}" "$@" 2>&1)"; then
    printf -v "${name}" '%s' "${output}"
    return 0
  fi
  fail "${name} exits 0" "'$*' exited non-zero: ${output}"
  printf -v "${name}" '%s' "${output}"
  return 1
}

DRY_OUT=""
capture DRY_OUT --dry-run || true

# 1. Snapshot discovery
assert_contains "dry-run discovers the latest automated snapshot" "${DRY_OUT}" "describe-db-snapshots"
assert_contains "dry-run names the source instance" "${DRY_OUT}" "Source instance"

# 2. Temp instance (never the source)
assert_contains "dry-run restores into a temp instance" "${DRY_OUT}" "restore-db-instance-from-db-snapshot"

# 3. Migrate
assert_contains "dry-run runs migrate against the temp instance" "${DRY_OUT}" "migrate"

# 4. DB verification, never an HTTP health check (the root-cause fix)
assert_contains "verification is a database connectivity probe" "${DRY_OUT}" "pg_isready"
assert_contains "verification probes row-count parity" "${DRY_OUT}" "parity"
assert_not_contains "verification never curls the DB endpoint as HTTP" "${DRY_OUT}" "curl"

# 5. RTO report
assert_contains "dry-run emits the RTO JSON report" "${DRY_OUT}" "rto_seconds"
assert_contains "report includes rto_within_target" "${DRY_OUT}" "rto_within_target"

# 6. Teardown
assert_contains "dry-run tears the temp instance down" "${DRY_OUT}" "delete-db-instance"

# 9. Missing aws CLI rejected with a clear error (live path — dry-run must
#    not require any tooling). PATH keeps only bash's own directory so the
#    script can launch while aws/psql are gone.
AWS_OUT=""
BASH_ONLY_PATH="$(dirname "$(command -v bash)")"
if PATH="${BASH_ONLY_PATH}" bash "${RDS_SCRIPT}" --target-rto-seconds 600 >/dev/null 2>&1; then
  fail "missing aws CLI rejected" "exit 0 with aws removed from PATH"
else
  AWS_OUT="$(PATH="${BASH_ONLY_PATH}" bash "${RDS_SCRIPT}" --target-rto-seconds 600 2>&1 || true)"
  assert_contains "missing aws CLI rejected with a clear error" "${AWS_OUT}" "aws CLI not found in PATH"
  pass "missing aws CLI rejected"
fi

# 10. Unknown args rejected
if bash "${RDS_SCRIPT}" --dry-run --bogus >/dev/null 2>&1; then
  fail "unknown arguments rejected" "exit 0 with --bogus"
else
  pass "unknown arguments rejected"
fi

# 7-8. --verify-db against a real Postgres (reachability-gated)
if [[ -n "${VERIFY_DB_URL:-}" ]]; then
  VERIFY_OUT=""
  capture VERIFY_OUT --verify-db "${VERIFY_DB_URL}" || true
  assert_contains "verify-db runs a connectivity probe" "${VERIFY_OUT}" "pg_isready"
  assert_contains "verify-db runs parity probes" "${VERIFY_OUT}" "parity"
  assert_contains "verify-db names the probed tables" "${VERIFY_OUT}" "tenants"

  if bash "${RDS_SCRIPT}" --verify-db "postgresql://nobody:nothing@127.0.0.1:1/nodb" >/dev/null 2>&1; then
    fail "unreachable database fails non-zero" "exit 0 against 127.0.0.1:1"
  else
    pass "unreachable database fails non-zero"
  fi
else
  skip "verify-db runs against a real Postgres" "VERIFY_DB_URL unset (set it to run the real probe)"
  skip "unreachable database fails non-zero" "VERIFY_DB_URL unset"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " test_restore_verify_rds.sh — ${PASS} passed / ${FAIL} failed / ${SKIP} skipped"
echo "════════════════════════════════════════════════════════════"
for t in "${TESTS[@]}"; do echo "  $t"; done
[[ "${FAIL}" -eq 0 ]]
