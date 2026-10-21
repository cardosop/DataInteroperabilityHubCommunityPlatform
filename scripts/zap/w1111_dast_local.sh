#!/usr/bin/env bash
# =============================================================================
# scripts/zap/w1111_dast_local.sh — W11.11 local DAST runner (compose staging)
#
# Runs the SAME pipeline the GitHub workflow runs, against the local
# compose staging stack (make staging-up / staging-post-deploy first):
#
#   1. public baseline scan   — zap-baseline.py (unauthenticated)
#   2. per-role authenticated scans — real login via
#      w1111_zap_auth_config.py (the CI auth script) + zap-full-scan.py
#      with the Authorization replacer config
#   3. per-report token-verification (the minted token must not be in
#      the report)
#   4. GATE-64 delta — check_zap_delta.py per surface vs the committed
#      baselines; --promote-baselines copies today's reports into
#      docs/security/zap/baselines/ (the re-baseline step; see
#      docs/runbooks/w1111-dast-zap.md for the triage contract)
#
# Credentials: the role personas are the E2E personas seeded by
# `ensure_e2e_user_roles` (emails committed in that command's source);
# their password is supplied by the operator at RUNTIME via
# DAST_LOCAL_PASSWORD — deliberately NO committed fallback (G12).
#   PLATFORM_ADMIN   e2e_platform@example.com
#   TENANT_ADMIN     e2e_admin@example.com
#   DATA_PROVIDER    e2e_test@example.com
#   DATA_CONSUMER    e2e_consumer@example.com
#   AUDITOR          e2e_auditor@example.com
#
# Usage:
#   DAST_LOCAL_PASSWORD=... make dast-local            # scan + delta gate
#   DAST_LOCAL_PASSWORD=... make dast-local REBASELINE=1  # scan + promote baselines
#   DAST_LOCAL_PASSWORD=... make dast-local ROLE=AUDITOR  # single surface
#
# Exit codes: 0 = zero new highs; 1 = new highs / missing reports.
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TARGET="${DAST_LOCAL_TARGET:-http://localhost:8101}"
API_TARGET="${TARGET}/api/v1/"
WORKDIR="${DAST_WORKDIR:-$ROOT/.zap-work}"
OUTDIR="${DAST_OUTDIR:-$ROOT/docs/security/zap/reports}"
MANIFEST="$ROOT/scripts/zap/w1111_role_matrix.json"
ZAP_IMAGE="${ZAP_IMAGE:-zaproxy/zap-stable}"
SCAN_MINUTES="${DAST_SCAN_MINUTES:-25}"
ROLE_FILTER="${ROLE:-}"

mkdir -p "$WORKDIR" "$OUTDIR"

log() { echo "[dast-local] $*"; }

require_password() {
  if [[ -z "${DAST_LOCAL_PASSWORD:-}" ]]; then
    echo "error: DAST_LOCAL_PASSWORD is required (the seeded E2E persona password — never committed)" >&2
    exit 2
  fi
}

# persona_email ROLE — the seeded E2E persona for the role (emails are
# committed in ensure_e2e_user_roles.py; not secrets).
persona_email() {
  case "$1" in
    PLATFORM_ADMIN) echo "e2e_platform@example.com" ;;
    TENANT_ADMIN) echo "e2e_admin@example.com" ;;
    DATA_PROVIDER) echo "e2e_test@example.com" ;;
    DATA_CONSUMER) echo "e2e_consumer@example.com" ;;
    AUDITOR) echo "e2e_auditor@example.com" ;;
    *) echo "error: no persona mapping for role $1" >&2; exit 2 ;;
  esac
}

surfaces() {
  python3 - "$MANIFEST" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1]))
for surface in manifest["surfaces"]:
    print(f"{surface['key']}\t{surface['report_file']}\t{surface['authenticated']}")
PY
}

# write_plan ROLE — the OpenAPI-driven automation plan for one role.  The
# API root carries no link surface (JSON-only), so the traditional spider
# crawl stops at ~7 URLs — the W11.11 first-run coverage gap.  The plan
# imports a REDUCED copy of the live OpenAPI spec (the full drf-spectacular
# output is ~12 MB and ZAP's importer never finishes on it; the reducer
# is structurally identity-preserving — see w1111_reduce_spec.py) and
# active-scans the resulting context; the replacer properties inject the
# bearer token into every request.
write_plan() {
  local role="$1"
  cat > "$WORKDIR/w1111-plan.yaml" <<PLAN
env:
  contexts:
    - name: dast
      urls:
        - $API_TARGET
  parameters:
    failOnError: true
    progressToStdout: false
jobs:
  - type: passiveScan-config
    parameters:
      enableTags: false
      maxAlertsPerRule: 10
  - type: openapi
    parameters:
      apiUrl: $SPEC_SERVE_URL/openapi-reduced.json
      # The spec's paths are absolute (/api/v1/...) — the target must be
      # the ORIGIN or every scanned URL doubles (/api/v1/api/v1/...).
      targetUrl: $TARGET
      context: dast
  - type: passiveScan-wait
    parameters:
      maxDuration: 5
  - type: activeScan
    parameters:
      context: dast
      maxRuleDurationInMins: 1
      maxScanDurationInMins: $SCAN_MINUTES
  - type: report
    parameters:
      template: traditional-json
      reportDir: /zap/wrk
      reportFile: $role
      reportTitle: $role
      reportDescription: $role
PLAN
}

# fetch_and_reduce_spec — download the live spec, reduce it, and serve
# ONLY the reduced file from a dedicated directory (never the workdir —
# it holds the minted token) bound to loopback.
SPEC_SERVE_DIR="${DAST_SPEC_SERVE_DIR:-/tmp/w1111-spec-serve}"
SPEC_SERVE_URL="http://localhost:${DAST_SPEC_SERVE_PORT:-18900}"
SPEC_SERVER_PID=""
fetch_and_reduce_spec() {
  mkdir -p "$SPEC_SERVE_DIR"
  curl -sf -m 60 "$TARGET/api/v1/openapi.json" -o "$SPEC_SERVE_DIR/openapi.json" \
    || { echo "error: cannot fetch the OpenAPI spec from $TARGET" >&2; exit 2; }
  python3 "$ROOT/scripts/zap/w1111_reduce_spec.py" \
    --input "$SPEC_SERVE_DIR/openapi.json" \
    --output "$SPEC_SERVE_DIR/openapi-reduced.json" >&2
  rm -f "$SPEC_SERVE_DIR/openapi.json"
  python3 -m http.server "${DAST_SPEC_SERVE_PORT:-18900}" \
    --bind 127.0.0.1 --directory "$SPEC_SERVE_DIR" >/dev/null 2>&1 &
  SPEC_SERVER_PID=$!
  # Cleanup: never leave the spec server (or a stray ZAP) behind.
  trap '[[ -n "$SPEC_SERVER_PID" ]] && kill "$SPEC_SERVER_PID" 2>/dev/null || true' EXIT
  sleep 1
}

# ── 1. Scans ────────────────────────────────────────────────────────────────
while IFS=$'\t' read -r key report_file authenticated; do
  if [[ -n "$ROLE_FILTER" && "$key" != "$ROLE_FILTER" ]]; then
    continue
  fi
  report="$WORKDIR/$report_file"

  if [[ "$authenticated" == "False" ]]; then
    log "public baseline scan → $report"
    docker run --rm --network host \
      -v "$WORKDIR:/zap/wrk:rw" -w /zap/wrk \
      "$ZAP_IMAGE" zap-baseline.py \
      -t "$API_TARGET" -J "$report_file" -T "$SCAN_MINUTES" \
      || log "baseline scan reported alerts (recorded; the delta gate decides)"
  else
    require_password
    email="$(persona_email "$key")"
    log "authenticated scan ($key as $email) → $report"
    python3 "$ROOT/scripts/zap/w1111_zap_auth_config.py" login-config \
      --target "$TARGET" \
      --username "$email" \
      --password-env DAST_LOCAL_PASSWORD \
      --output "$WORKDIR/w1111-replacer.properties" \
      --token-file "$WORKDIR/dast.token"
    # OpenAPI-driven plan (the same shape the CI workflow runs); -port
    # avoids the host's traefik 8080.
    fetch_and_reduce_spec
    write_plan "$report_file"
    # timeout: the plan's report job writes the JSON BEFORE the JVM
    # exits, and the JVM can hang post-plan (headless-Firefox/geckodriver
    # cleanup on scan-heavy runs — seen live: the plan "succeeded" and
    # the process never exited). The report survives either way; the
    # leftover container is force-removed.
    # 65 min: import (~5) + passive-wait (5) + active (SCAN_MINUTES) +
    # report (~2) + hang-margin — the 27.5-min first draft killed the
    # scan mid-active (the report job never ran).
    timeout "$((SCAN_MINUTES * 3 + 2100))" docker run --rm --name w1111-zap-scan \
      --network host \
      -v "$WORKDIR:/zap/wrk:rw" -w /zap/wrk \
      "$ZAP_IMAGE" zap.sh -port 18080 -cmd \
      -autorun /zap/wrk/w1111-plan.yaml \
      -configfile /zap/wrk/w1111-replacer.properties \
      || log "scan reported alerts (recorded; the delta gate decides)"
    docker rm -f w1111-zap-scan >/dev/null 2>&1 || true
    python3 "$ROOT/scripts/zap/w1111_zap_auth_config.py" verify-report \
      --report "$WORKDIR/$report_file" \
      --token-file "$WORKDIR/dast.token"
  fi

  cp "$WORKDIR/$report_file" "$OUTDIR/$report_file"
  log "report saved to $OUTDIR/$report_file"
done < <(surfaces)

# ── 2. Delta gate (GATE-64) ─────────────────────────────────────────────────
log "delta gate vs committed baselines"
python3 "$ROOT/scripts/zap/w1111_delta_run.py" \
  --input-dir "$WORKDIR" \
  --out-dir "$WORKDIR/delta-out"

# ── 3. Optional baseline promotion (the deliberate re-baseline step) ────────
if [[ "${REBASELINE:-0}" == "1" ]]; then
  log "promoting today's reports into docs/security/zap/baselines/ (re-baseline)"
  python3 - "$MANIFEST" "$WORKDIR" "$ROOT/docs/security/zap/baselines" <<'PY'
import json
import shutil
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text())
workdir = Path(sys.argv[2])
baseline_dir = Path(sys.argv[3])
baseline_dir.mkdir(parents=True, exist_ok=True)
for surface in manifest["surfaces"]:
    src = workdir / surface["report_file"]
    if not src.is_file():
        print(f"error: missing report for {surface['key']}: {src}", file=sys.stderr)
        sys.exit(1)
    dst = baseline_dir / surface["baseline"]
    shutil.copyfile(src, dst)
    print(f"promoted {surface['key']}: {src} → {dst}")
PY
fi

log "done — delta reports in $WORKDIR/delta-out"
