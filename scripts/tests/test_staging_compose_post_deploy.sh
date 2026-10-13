#!/usr/bin/env bash
# =============================================================================
# scripts/tests/test_staging_compose_post_deploy.sh
#
# W0.8 (oss-release-remediation) — LIVE post-deploy verification of the
# hardened staging stack. The static contract suites pin the compose FILE
# (test_staging_exposure_contract.py); this suite pins the DEPLOYED stack:
#
#   1. the resolved compose config parses and carries NO defaulted
#      credentials (the `:-admin` / `:-hub` / `:-prefect` class)
#   2. every redis URL in the RESOLVED config is authenticated
#   3. redis x4: unauthenticated PING is REFUSED (NOAUTH) and each
#      provisioned per-instance password connects (PONG) — passwords are
#      read from .env.staging and NEVER echoed
#   4. grafana: wrong password → 401 and the provisioned password → 200
#      on /api/org (the authenticated probe surface — /api/health is
#      deliberately unauthenticated in Grafana 11, so the W0.7 evidence
#      boot's probe surface is refined here)
#   5. observability published ports (prometheus/grafana/alertmanager/
#      jaeger) are loopback-bound AT RUNTIME (ss -ltn / ss -lun), never
#      0.0.0.0
#   6. the queue services resolve rq.serializers.JSONSerializer at
#      runtime (printenv inside the running container, not the file)
#   7. every stack service is UP — the pin that catches the W0.8 root
#      causes: the worker-service "Authentication required." redis crash
#      and the prefect-integration auth-mode crash-loop
#   8. the API /health/live/ returns 200 on the published port
#
# Environment policy (W16): when the stack (or .env.staging) is absent
# the suite SKIPS locally (exit 0, noted) and RAISES under CI=true — an
# env-dependent verification may never silently pass in CI.
#
# Usage: bash scripts/tests/test_staging_compose_post_deploy.sh
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
cd "${REPO_ROOT}"

# Overridable for drills and CI variations (the RED-first drill points
# STAGING_PROJECT at a nonexistent project to prove the W16 raise).
PROJECT="${STAGING_PROJECT:-hub-staging}"
COMPOSE_FILE="${STAGING_COMPOSE_FILE:-docker-compose.staging.yml}"
ENV_FILE="${STAGING_ENV_FILE:-.env.staging}"

DC=(docker compose --project-name "${PROJECT}" -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}")

PASS=0
FAIL=0
TESTS=()

pass() { PASS=$((PASS + 1)); TESTS+=("PASS: $1"); }
fail() { FAIL=$((FAIL + 1)); TESTS+=("FAIL: $1 — $2"); }

# ── Environment policy gate (W16) ────────────────────────────────────────────
skip_or_raise() {
  local reason="$1"
  if [[ "${CI:-}" == "true" ]]; then
    echo "FAILED: ${reason} — CI=true raises (W16 environment policy)"
    exit 1
  fi
  echo "SKIPPED: ${reason} — local runs keep the graceful skip (W16)"
  exit 0
}

if ! command -v ss >/dev/null 2>&1; then
  skip_or_raise "ss is not installed (the loopback probe needs it)"
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  skip_or_raise "${ENV_FILE} missing (gitignored secret material)"
fi
if [[ -z "$("${DC[@]}" ps -q 2>/dev/null || true)" ]]; then
  skip_or_raise "the ${PROJECT} stack is not up"
fi

# ── Helpers ──────────────────────────────────────────────────────────────────
# env_value prints the env-file value (empty when unset). Values are
# NEVER echoed by the suite — failures name the key only.
env_value() {
  grep -E "^${1}=" "${ENV_FILE}" 2>/dev/null | head -1 | cut -d= -f2- | tr -d '"[[:space:]]'
}

redis_probe() {
  local instance="$1" var="$2"
  local unauth auth pw
  # Unauthenticated PING must be REFUSED (the requirepass runtime pin).
  unauth="$("${DC[@]}" exec -T "${instance}" redis-cli PING 2>&1 || true)"
  if grep -q "NOAUTH" <<< "${unauth}"; then
    pass "${instance}: unauthenticated PING refused (NOAUTH)"
  else
    fail "${instance}: unauthenticated PING refused (NOAUTH)" \
      "PING without auth was answered, not refused (output not echoed)"
  fi
  # The provisioned password must connect — REDISCLI_AUTH env, never argv.
  pw="$(env_value "${var}")"
  if [[ -z "${pw}" ]]; then
    fail "${instance}: provisioned password connects (PONG)" \
      "${var} missing from ${ENV_FILE} (value not echoed)"
    return
  fi
  auth="$(REDISCLI_AUTH="${pw}" "${DC[@]}" exec -T -e REDISCLI_AUTH="${pw}" \
    "${instance}" redis-cli PING 2>&1 || true)"
  if grep -q "PONG" <<< "${auth}"; then
    pass "${instance}: provisioned password connects (PONG)"
  else
    fail "${instance}: provisioned password connects (PONG)" \
      "authenticated PING failed (output not echoed)"
  fi
}

# ── 1. The resolved config: parses, no defaulted credentials ─────────────────
RESOLVED="$("${DC[@]}" config 2>/dev/null || true)"
if [[ -z "${RESOLVED}" ]]; then
  fail "resolved compose config parses" "docker compose config failed (stderr not echoed)"
else
  pass "resolved compose config parses"
fi
if grep -qE ':-admin|:-hub|:-prefect' <<< "${RESOLVED}"; then
  fail "resolved config has no defaulted credentials" \
    "a :-admin / :-hub / :-prefect default survived resolution"
else
  pass "resolved config has no defaulted credentials"
fi

# ── 2. Every redis URL in the RESOLVED config is authenticated ───────────────
REDIS_URLS="$(grep -oE 'redis://[^"[:space:]]+' <<< "${RESOLVED}" || true)"
if [[ -z "${REDIS_URLS}" ]]; then
  fail "resolved redis URLs authenticated" "no redis URLs found — the pin is vacuous"
else
  BAD_URL=0
  while IFS= read -r url; do
    # Authenticated form: redis://:password@host:port/db (the empty-user
    # convention settings.py documents). Never echoed — it carries the
    # password.
    if [[ "${url}" != redis://:*@* ]]; then
      BAD_URL=1
      fail "resolved redis URLs authenticated" \
        "an unauthenticated URL resolves (value not echoed)"
      break
    fi
  done <<< "${REDIS_URLS}"
  [[ "${BAD_URL}" -eq 0 ]] && pass "resolved redis URLs authenticated"
fi

# ── 3. redis x4: refusal + provisioned passwords at runtime ──────────────────
redis_probe redis-cache REDIS_CACHE_PASSWORD
redis_probe redis-queue REDIS_QUEUE_PASSWORD
redis_probe redis-events REDIS_EVENTS_PASSWORD
redis_probe redis-channels REDIS_CHANNELS_PASSWORD

# ── 4. grafana: wrong password 401, provisioned password 200 ─────────────────
GF_PORT="$(env_value GRAFANA_PORT)"
GF_PORT="${GF_PORT:-3001}"
GF_USER="$(env_value GRAFANA_ADMIN_USER)"
GF_USER="${GF_USER:-admin}"
GF_PW="$(env_value GRAFANA_ADMIN_PASSWORD)"
if [[ -z "${GF_PW}" ]]; then
  fail "grafana: provisioned password authenticates (200)" \
    "GRAFANA_ADMIN_PASSWORD missing from ${ENV_FILE} (value not echoed)"
else
  # The auth pairs are built into VARIABLES first — the suite never
  # carries a literal `-u user:password` shape (a synthetic sentinel
  # literal would still trip secret scanners), and the real password
  # stays env-sourced and never echoed.
  GF_WRONG_CRED="${GF_USER}:wrong-password-probe"
  GF_WRONG="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 \
    -u "${GF_WRONG_CRED}" "http://127.0.0.1:${GF_PORT}/api/org" 2>/dev/null || true)"
  if [[ "${GF_WRONG}" == "401" ]]; then
    pass "grafana: wrong password rejected (401)"
  else
    fail "grafana: wrong password rejected (401)" "got HTTP ${GF_WRONG:-no-response}"
  fi
  GF_REAL_CRED="${GF_USER}:${GF_PW}"
  GF_RIGHT="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 \
    -u "${GF_REAL_CRED}" "http://127.0.0.1:${GF_PORT}/api/org" 2>/dev/null || true)"
  if [[ "${GF_RIGHT}" == "200" ]]; then
    pass "grafana: provisioned password authenticates (200)"
  else
    fail "grafana: provisioned password authenticates (200)" \
      "got HTTP ${GF_RIGHT:-no-response} (password not echoed)"
  fi
fi

# ── 5. Observability published ports loopback-bound AT RUNTIME ───────────────
# service:container-port:proto — the four observability surfaces' published
# ports. `docker compose port` resolves the host side (env overrides and
# all), then ss proves the actual LISTEN binding is loopback-only.
OBSERVABILITY="prometheus:9090:tcp grafana:3000:tcp alertmanager:9093:tcp jaeger:16686:tcp jaeger:14268:tcp jaeger:6831:udp"
for entry in ${OBSERVABILITY}; do
  svc="${entry%%:*}"
  rest="${entry#*:}"
  cport="${rest%%:*}"
  proto="${rest##*:}"
  if [[ "${proto}" == "udp" ]]; then
    binding="$("${DC[@]}" port --protocol udp "${svc}" "${cport}" 2>/dev/null || true)"
  else
    binding="$("${DC[@]}" port "${svc}" "${cport}" 2>/dev/null || true)"
  fi
  if [[ -z "${binding}" ]]; then
    fail "${svc}:${cport} published and loopback-bound" "no published port found"
    continue
  fi
  host_port="${binding##*:}"
  if [[ "${binding}" != 127.0.0.1:* && "${binding}" != "[::1]:"* ]]; then
    fail "${svc}:${cport} published loopback-only" "published as ${binding} — not loopback"
    continue
  fi
  ss_opts=(-ltn)
  [[ "${proto}" == "udp" ]] && ss_opts=(-lun)
  if ss "${ss_opts[@]}" 2>/dev/null | grep -qE "127\.0\.0\.1:${host_port}[[:space:]]|\[::1\]:${host_port}[[:space:]]"; then
    pass "${svc}:${cport} LISTENs on loopback:${host_port} (runtime)"
  else
    fail "${svc}:${cport} LISTENs on loopback:${host_port} (runtime)" \
      "the published loopback bind is not LISTENing"
  fi
  if ss "${ss_opts[@]}" 2>/dev/null | grep -qE "0\.0\.0\.0:${host_port}[[:space:]]"; then
    fail "${svc}:${cport} never on 0.0.0.0" "the port ALSO LISTENs on 0.0.0.0"
  else
    pass "${svc}:${cport} not LISTENing on 0.0.0.0"
  fi
done

# ── 6. Queue services resolve the JSON serializer at runtime ─────────────────
for svc in api-service worker-service compliance-service compliance-rq-worker dq-service datacontract-service; do
  value="$("${DC[@]}" exec -T "${svc}" printenv RQ_SERIALIZER 2>/dev/null || true)"
  if [[ "${value}" == "rq.serializers.JSONSerializer" ]]; then
    pass "${svc}: RQ_SERIALIZER=JSONSerializer at runtime"
  else
    fail "${svc}: RQ_SERIALIZER=JSONSerializer at runtime" \
      "got '${value:-unset-or-service-down}'"
  fi
done

# ── 7. Every stack service is UP (the W0.8 root-cause pin) ───────────────────
# `ps -a` includes the one-shot init services (minio-init completes and
# leaves the running list — `service_completed_successfully` consumers
# still need it to have Exited 0, not crashed).
STATUSES="$("${DC[@]}" ps -a --format '{{.Service}}\t{{.Status}}' 2>/dev/null || true)"
for svc in $("${DC[@]}" config --services 2>/dev/null || true); do
  line="$(grep -P "^${svc}\t" <<< "${STATUSES}" | head -1 || true)"
  if [[ -z "${line}" ]]; then
    fail "${svc} is UP" "no container state found (not created?)"
  elif [[ "${line}" == *"Up"* ]]; then
    pass "${svc} is UP"
  elif [[ "${line}" == *"Exited (0)"* ]]; then
    pass "${svc} completed (one-shot init, Exited 0)"
  else
    fail "${svc} is UP" "state: ${line#*$'\t'}"
  fi
done

# ── 8. API liveness on the published port ────────────────────────────────────
API_PORT="$(env_value API_PORT)"
API_PORT="${API_PORT:-8000}"
API_CODE="$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 \
  "http://127.0.0.1:${API_PORT}/health/live/" 2>/dev/null || true)"
if [[ "${API_CODE}" == "200" ]]; then
  pass "API /health/live/ responds 200 on :${API_PORT}"
else
  fail "API /health/live/ responds 200 on :${API_PORT}" "got HTTP ${API_CODE:-no-response}"
fi

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "───────────────────────────────────────────────────────────"
echo "  ${PASS} passed, ${FAIL} failed"
for t in "${TESTS[@]}"; do echo "  ${t}"; done
echo "───────────────────────────────────────────────────────────"
if [[ "${FAIL}" -gt 0 ]]; then
  echo "FAILED"
  exit 1
fi
echo "PASSED"
