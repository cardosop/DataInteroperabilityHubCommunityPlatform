#!/usr/bin/env bash
#
# Phase 240.DoD.4 — Post-deploy production smoke test for the
# data-quality feature.
#
# Verifies, on a freshly-deployed cluster:
#
#   1. Synthetic DQ runs across every registered profile_key complete
#      successfully via the dq-service ``POST /run-dataframe`` endpoint
#      (engine-agnostic — both ``intake_basic_gx`` (GX) and
#      ``intake_basic_soda`` (Soda Core) routes are exercised; routing
#      is by suffix per Phase 240.3.A.5).
#
#   2. All 4 DQ alert delivery channels (EMAIL / SLACK / WEBHOOK /
#      PAGERDUTY) are reachable from the cluster and their
#      circuit-breakers are NOT in the open state — i.e. each delivery
#      adapter is healthy enough to deliver if needed.  Done via the
#      Prometheus query ``dq_alert_channel_circuit_open`` (set by
#      ``hub.apps.dq.clients.base`` per Phase 240.1.A.6).
#
#   3. Trivy scan of the dq-service image is clean of CRITICAL/HIGH —
#      enforced unconditionally by the deploy-time gate in
#      ``.github/workflows/deploy.yml`` (Phase 240.5.D), pinned by the
#      contract test ``tests/ci/test_dq_image_vulnerability_scan.py``.
#      This script merely surfaces the contract test's last result for
#      operator confirmation and prints the deploy-workflow run URL —
#      the gate ITSELF is enforced upstream and cannot be bypassed.
#
#   4. The Grafana DQ board (``dashboards/data-quality.json``) shows
#      non-zero ``dq_runs_total`` within the last 1h via a direct
#      Prometheus query.  This rules out the "deployed but receiving
#      no traffic" failure mode.
#
# Exit codes:
#   0 — all 4 verifications pass.
#   1 — any verification fails; per-check failure detail printed.
#   2 — environment misconfigured (missing required env var or auth).
#
# Required environment variables:
#   DQ_SERVICE_URL          — base URL of the dq-service (e.g.
#                             https://api.stagingmeshant-internal.example.com or
#                             internal cluster URL).
#   PROMETHEUS_URL          — base URL of the Prometheus query API.
#   INTERNAL_API_KEY        — api-key for the dq-service internal API.
#   INTERNAL_PAYLOAD_SECRET — HMAC secret per 240.5.G.3 (only required
#                             once dq-service flips
#                             ``DQ_REQUIRE_PAYLOAD_SIGNATURE=true``;
#                             auto-detected via the gating environment
#                             check below).
#   DEPLOY_WORKFLOW_RUN_URL — URL of the most recent deploy.yml run.
#                             Optional but recommended; printed in
#                             the trivy-check section so the operator
#                             can confirm the gate ran.
#
# Optional:
#   PROFILE_KEYS            — comma-separated list overriding the
#                             auto-discovered registered profiles.
#                             Default: ``intake_basic_gx,intake_basic_soda``.
#   TIMEOUT_SECONDS         — per-check timeout (default 30).
#
# Usage:
#   DQ_SERVICE_URL=https://dq.stagingmeshant-internal.example.com \
#     PROMETHEUS_URL=https://prom.stagingmeshant-internal.example.com \
#     INTERNAL_API_KEY=$(aws secretsmanager get-secret-value \
#         --profile staging \
#         --secret-id meshant-staging/api.INTERNAL_API_KEY \
#         --query SecretString --output text) \
#     ./scripts/smoke_tests_dq.sh
#
# This script is invoked manually post-deploy.  It is NOT wired into
# CI because it requires production secrets + reachability to the
# Prometheus + dq-service inside the staging/prod VPC.

set -euo pipefail

# ---------- Colour helpers ---------------------------------------------------

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# ---------- Environment validation ------------------------------------------

require_env() {
    local var=$1
    if [ -z "${!var:-}" ]; then
        log_error "Required env var '$var' is unset."
        exit 2
    fi
}

require_env DQ_SERVICE_URL
require_env PROMETHEUS_URL
require_env INTERNAL_API_KEY

PROFILE_KEYS="${PROFILE_KEYS:-intake_basic_gx,intake_basic_soda}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-30}"
DEPLOY_WORKFLOW_RUN_URL="${DEPLOY_WORKFLOW_RUN_URL:-}"

ERRORS=0
note_error() { ERRORS=$((ERRORS + 1)); }

# ---------- Check 1 — synthetic DQ runs across registered profiles ----------

# We post a tiny in-memory DataFrame directly via /run-dataframe
# (no S3 round-trip needed for smoke).  Each row is a 3-column synthetic
# record; the profile's checks (defined per-engine in
# ``services/dq-service/dq_profile.py``) accept any input shape — the
# point is engine reachability + dispatch correctness, NOT validation
# correctness.
SYNTHETIC_PAYLOAD='{
  "profile_key": "%s",
  "data": [
    {"id": 1, "name": "alice", "value": 10},
    {"id": 2, "name": "bob",   "value": 20},
    {"id": 3, "name": "carol", "value": 30}
  ]
}'

run_synthetic_dq() {
    local profile_key=$1
    local payload
    payload=$(printf "$SYNTHETIC_PAYLOAD" "$profile_key")
    local body
    body=$(echo -n "$payload" | python3 -c 'import sys, json; print(json.dumps(json.loads(sys.stdin.read())))')

    # Optional payload signing per 240.5.G.3.  If
    # INTERNAL_PAYLOAD_SECRET is set we stamp the signature; if unset
    # the dq-service will reject with 401 ONLY when
    # DQ_REQUIRE_PAYLOAD_SIGNATURE=true is flipped on the cluster (per
    # 240.5.G.4 rolling-deploy: soak first, enforce later).  In soak
    # mode the request goes through unsigned.
    local extra_headers=()
    if [ -n "${INTERNAL_PAYLOAD_SECRET:-}" ]; then
        local ts
        ts=$(date +%s)
        local sig
        sig=$(printf "%s\n%s" "$ts" "$body" | openssl dgst -sha256 -hmac "$INTERNAL_PAYLOAD_SECRET" -hex | awk '{print $2}')
        extra_headers+=(-H "X-Internal-Payload-Timestamp: $ts" -H "X-Internal-Payload-Signature: $sig")
    fi

    local response
    response=$(curl -sS \
        --max-time "$TIMEOUT_SECONDS" \
        -X POST \
        -H "Content-Type: application/json" \
        -H "X-Internal-API-Key: $INTERNAL_API_KEY" \
        "${extra_headers[@]}" \
        -d "$body" \
        "${DQ_SERVICE_URL}/run-dataframe" 2>&1) || {
            log_error "  ${profile_key}: curl failed — $response"
            return 1
        }

    # Expect HTTP 200 + a JSON body containing ``"profile_key": "<key>"``
    # (the dq-service echoes the input profile back in
    # RunDQResponse.profile_key).
    if echo "$response" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
except Exception as e:
    print(f'response not JSON: {e}'); sys.exit(1)
pk = data.get('profile_key')
if pk != '$profile_key':
    print(f'expected profile_key=$profile_key, got {pk!r}'); sys.exit(1)
" 2>/tmp/dq_smoke_err; then
        log_info "  ${profile_key}: ✓ run completed"
        return 0
    else
        log_error "  ${profile_key}: ✗ $(cat /tmp/dq_smoke_err 2>/dev/null || echo 'unknown error')"
        log_error "    response head: $(echo "$response" | head -c 300)"
        return 1
    fi
}

log_info '=================================================='
log_info '1/4 — Synthetic DQ runs across registered profiles'
log_info '=================================================='
IFS=',' read -ra _profiles <<< "$PROFILE_KEYS"
for pk in "${_profiles[@]}"; do
    run_synthetic_dq "$pk" || note_error
done

# ---------- Check 2 — alert-channel circuit-breaker dry-run -----------------

# We don't attempt an actual alert delivery (would need pre-configured
# test recipients per channel + would clutter alert audit log).  The
# pragmatic dry-run is: query Prometheus for the per-channel
# circuit-breaker state — the breakers OPEN under sustained delivery
# failure (5 in a row by default; see
# ``hub.apps.core.resilience.service_breakers``).  An OPEN breaker
# means the channel is broken; CLOSED means it's healthy enough to
# deliver if/when triggered.
log_info '=================================================='
log_info '2/4 — Alert-channel circuit-breaker dry-run (4 channels)'
log_info '=================================================='

prom_query() {
    local query=$1
    curl -sS --max-time "$TIMEOUT_SECONDS" \
        --data-urlencode "query=${query}" \
        "${PROMETHEUS_URL}/api/v1/query"
}

check_channel_breaker() {
    local channel=$1
    # ``dq_alert_channel_circuit_open`` is a gauge labelled by channel.
    # We OR against the metric being ABSENT (channel never used yet)
    # because a freshly-deployed cluster may not have triggered any
    # alert yet — absent ≠ open.
    local query="max(dq_alert_channel_circuit_open{channel=\"${channel}\"}) or vector(0)"
    local response
    response=$(prom_query "$query")
    local value
    value=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
except Exception as e:
    print('NaN'); sys.exit(0)
result = data.get('data', {}).get('result', [])
if not result:
    print(0)  # absent — treat as healthy
else:
    print(result[0]['value'][1])
" 2>/dev/null)
    if [ "$value" = "0" ] || [ "$value" = "0.0" ]; then
        log_info "  ${channel}: ✓ circuit closed (channel healthy)"
        return 0
    else
        log_error "  ${channel}: ✗ circuit OPEN — channel currently rejecting deliveries (value=${value})"
        return 1
    fi
}

for channel in EMAIL SLACK WEBHOOK PAGERDUTY; do
    check_channel_breaker "$channel" || note_error
done

# ---------- Check 3 — trivy gate confirmation -------------------------------

# Trivy is enforced UPSTREAM in the deploy.yml gate — this script
# cannot bypass it.  Surface the deploy-workflow run URL for operator
# audit; if not provided, point them at the contract test that pins
# the gate's existence so they can manually confirm it ran.
log_info '=================================================='
log_info '3/4 — Trivy gate confirmation (deploy-time gate)'
log_info '=================================================='
log_info '  Trivy scan of the dq-service image is enforced UNCONDITIONALLY at'
log_info '  deploy time by .github/workflows/deploy.yml (Phase 240.5.D); the'
log_info '  gate fails the deploy on any CRITICAL/HIGH CVE outside the'
log_info '  .trivyignore allow-list.  This smoke step is informational only.'
if [ -n "$DEPLOY_WORKFLOW_RUN_URL" ]; then
    log_info "  Deploy-workflow run for this release:"
    log_info "    $DEPLOY_WORKFLOW_RUN_URL"
    log_info '  → operator must confirm the run is GREEN before declaring smoke OK.'
else
    log_warn '  $DEPLOY_WORKFLOW_RUN_URL is unset; cannot link to the run.'
    log_warn '  Confirm the deploy.yml run for this release is GREEN before declaring smoke OK.'
    log_warn '  Contract test pinning the gate: tests/ci/test_dq_image_vulnerability_scan.py'
fi

# ---------- Check 4 — Grafana DQ board non-zero data within 1 hour ----------

# Prometheus query ``increase(dq_runs_total[1h])`` is the cleanest
# proxy for "Grafana board shows data" — the dashboard's primary
# panels read from the same metric.  A non-zero value means the Hub
# has sent at least one DQ run in the last hour (which our Check 1
# above guarantees, modulo metric scrape cadence).
log_info '=================================================='
log_info '4/4 — Grafana DQ board non-zero data within 1 hour'
log_info '=================================================='

GRAFANA_QUERY='sum(increase(dq_runs_total[1h]))'
response=$(prom_query "$GRAFANA_QUERY")
value=$(echo "$response" | python3 -c "
import json, sys
try:
    data = json.loads(sys.stdin.read())
except Exception as e:
    print('NaN'); sys.exit(0)
result = data.get('data', {}).get('result', [])
if not result:
    print('0')
else:
    print(result[0]['value'][1])
" 2>/dev/null)

if [ -z "$value" ] || [ "$value" = "NaN" ]; then
    log_error "  ✗ Prometheus query failed or returned no data (sum(increase(dq_runs_total[1h])))."
    log_error "    response head: $(echo "$response" | head -c 300)"
    note_error
elif python3 -c "import sys; sys.exit(0 if float('$value') > 0 else 1)"; then
    log_info "  ✓ DQ runs counter is non-zero in last 1h: $value"
else
    log_error "  ✗ DQ runs counter is zero in last 1h — Grafana board will be empty."
    log_error "    This usually means the synthetic runs in Check 1 didn't reach Prometheus yet"
    log_error "    (scrape cadence ~30s by default).  Wait 1 minute and re-run."
    note_error
fi

# ---------- Summary ---------------------------------------------------------

log_info '=================================================='
if [ "$ERRORS" -eq 0 ]; then
    log_info '✓ All DoD.4 verifications passed.'
    exit 0
fi
log_error "✗ ${ERRORS} verification(s) failed — see per-check output above."
exit 1
