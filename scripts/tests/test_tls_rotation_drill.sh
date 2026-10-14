#!/usr/bin/env bash
# =============================================================================
# scripts/tests/test_tls_rotation_drill.sh
#
# TDD contract suite for scripts/tls_rotation_drill.sh — the pilot-readiness
# 4.4 TLS rotation rehearsal. Pins the dry-run contract:
#   1. inspect probes the live TLS endpoint (openssl s_client) and reports
#      serial + notAfter + issuer
#   2. rotate-file snapshots the CURRENT cert/key before touching them
#   3. rotate-file installs the new pair atomically
#   4. rotate-file reloads the TLS terminator after the swap
#   5. rotate-file VERIFIES the served serial changed (polls the endpoint)
#   6. rotate-file rolls the old pair BACK on verification failure
#   7. rotate-file emits the rotation report JSON (old/new serial + status)
#   8. rotate-acme snapshots acme.json before the removal
#   9. rotate-acme removes the domain cert via scripts/tls_acme_json.py
#  10. rotate-acme restarts the TLS terminator to re-request
#  11. flags (--host/--cert-dir/--reload/--acme-domain) propagate
#  12. unknown arguments are rejected
#
# Usage: bash scripts/tests/test_tls_rotation_drill.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TLS_SCRIPT="${SCRIPT_DIR}/../tls_rotation_drill.sh"

if [[ ! -f "${TLS_SCRIPT}" ]]; then
  echo "FAILED: ${TLS_SCRIPT} does not exist (write it first — TDD RED)"
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

capture() {
  local name="$1"; shift
  local output
  if output="$(bash "${TLS_SCRIPT}" "$@" 2>&1)"; then
    printf -v "${name}" '%s' "${output}"
    return 0
  fi
  fail "${name} dry-run exits 0" "dry-run '$*' exited non-zero: ${output}"
  printf -v "${name}" '%s' "${output}"
  return 1
}

INSPECT_OUT=""
capture INSPECT_OUT --dry-run inspect --host api.stagingmeshant-internal.example.com:443 --sni api.stagingmeshant-internal.example.com || true

# 1. inspect probes the live endpoint
assert_contains "inspect probes with openssl s_client" "${INSPECT_OUT}" "openssl s_client"
assert_contains "inspect extracts the serial" "${INSPECT_OUT}" "-serial"
assert_contains "inspect extracts notAfter" "${INSPECT_OUT}" "-enddate"
assert_contains "inspect extracts the issuer" "${INSPECT_OUT}" "-issuer"
assert_contains "host flag propagates" "${INSPECT_OUT}" "api.stagingmeshant-internal.example.com:443"

ROTATE_OUT=""
capture ROTATE_OUT --dry-run rotate-file --host localhost:8443 --sni hub.local \
  --cert-dir /etc/traefik/certs --reload "docker restart traefik" || true

# 2. Snapshot BEFORE touching the pair
assert_contains "rotate-file snapshots the current pair first" "${ROTATE_OUT}" "snapshot"
assert_line_before "snapshot happens before the swap" "${ROTATE_OUT}" "snapshot" "install new"

# 3-4. Atomic install + reload
assert_contains "rotate-file installs the new pair" "${ROTATE_OUT}" "install new"
assert_contains "rotate-file reloads the terminator" "${ROTATE_OUT}" "docker restart traefik"
assert_line_before "reload happens after the swap" "${ROTATE_OUT}" "install new" "reload"

# 5. Verification of the served serial
assert_contains "rotate-file verifies the served serial changed" "${ROTATE_OUT}" "serial changed"
assert_contains "rotation verifies via the live endpoint" "${ROTATE_OUT}" "localhost:8443"

# 6. Rollback path exists
assert_contains "rotation has a rollback path" "${ROTATE_OUT}" "rollback"

# 7. Report
assert_contains "rotation emits the report JSON" "${ROTATE_OUT}" "old_serial"
assert_contains "report carries the new serial" "${ROTATE_OUT}" "new_serial"
assert_contains "report carries the status" "${ROTATE_OUT}" "status"

# 11. Flags
assert_contains "cert-dir flag propagates" "${ROTATE_OUT}" "/etc/traefik/certs"

ACME_OUT=""
capture ACME_OUT --dry-run rotate-acme --host api.stagingmeshant-internal.example.com:443 \
  --sni api.stagingmeshant-internal.example.com --acme-json /letsencrypt/acme.json \
  --acme-domain api.stagingmeshant-internal.example.com \
  --restart "docker compose restart traefik" || true

# 8-10. ACME path
assert_contains "rotate-acme snapshots acme.json first" "${ACME_OUT}" "acme.json"
assert_contains "rotate-acme removes the domain cert via tls_acme_json.py" "${ACME_OUT}" "tls_acme_json.py"
assert_contains "rotate-acme restarts the terminator to re-request" "${ACME_OUT}" "restart"
assert_contains "acme-domain flag propagates" "${ACME_OUT}" "api.stagingmeshant-internal.example.com"

# 12. Unknown args rejected
if bash "${TLS_SCRIPT}" --dry-run --bogus inspect >/dev/null 2>&1; then
  fail "unknown arguments rejected" "exit 0 with --bogus"
else
  pass "unknown arguments rejected"
fi

echo
echo "════════════════════════════════════════════════════════════"
echo " test_tls_rotation_drill.sh — ${PASS} passed / ${FAIL} failed"
echo "════════════════════════════════════════════════════════════"
for t in "${TESTS[@]}"; do echo "  $t"; done
[[ "${FAIL}" -eq 0 ]]
