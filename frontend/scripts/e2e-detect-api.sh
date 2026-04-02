#!/usr/bin/env bash
# Auto-detect backend API port (8000 = dev compose, 8001 = test compose) and run E2E.
# Use when backend is already running. No mocks/stubs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

# Fail fast with clear message when backend is unreachable
fail_no_backend() {
  echo "❌ Backend API is not reachable."
  echo ""
  echo "E2E tests require a running backend. From repo root:"
  echo "  • docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d   (API on 8000)"
  echo "  • docker compose -f docker-compose.test.yml up -d                        (API on 8001)"
  echo ""
  echo "Or use: npm run test:e2e:full  (starts backend automatically)"
  exit 1
}

# True when Vite (or any HTTP server) accepts GET / on the E2E web port.
# Prefer 127.0.0.1 first — avoids IPv6/localhost resolution differences with Node/Playwright.
curl_frontend_root() {
  local port="${1:?}"
  curl -sf --connect-timeout 3 --max-time 10 "http://127.0.0.1:${port}/" > /dev/null 2>&1 \
    || curl -sf --connect-timeout 3 --max-time 10 "http://localhost:${port}/" > /dev/null 2>&1
}

# Start npm run dev on port if nothing is listening; wait until HTTP answers.
# Sets FRONTEND_STARTED=true and EXIT trap when this process starts Vite (see bottom: no exec).
ensure_e2e_frontend_dev_server() {
  local port="${1:?}"
  if curl_frontend_root "$port"; then
    echo "Frontend already running at http://localhost:${port}"
    return 0
  fi
  echo "Starting frontend dev server on port ${port}..."
  VITE_WS_ENABLED=false VITE_E2E_TEST=true npm run dev -- --port "${port}" --strictPort &
  FRONTEND_PID=$!
  FRONTEND_STARTED=true
  trap 'kill "$FRONTEND_PID" 2>/dev/null || true' EXIT
  local i
  for i in $(seq 1 60); do
    if curl_frontend_root "$port"; then
      echo "Frontend ready at http://localhost:${port}"
      return 0
    fi
    if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
      echo "❌ Frontend process exited unexpectedly before becoming ready."
      echo "   Check: npm run dev -- --port ${port} --strictPort (strictPort fails if port is held by a stale process)"
      return 1
    fi
    sleep 2
  done
  echo "❌ Frontend failed to become ready within ~120s"
  kill "$FRONTEND_PID" 2>/dev/null || true
  return 1
}

# If VITE_API_BASE_URL is already set, still verify backend is reachable before running
if [[ -n "${VITE_API_BASE_URL:-}" ]]; then
  echo "Using VITE_API_BASE_URL=${VITE_API_BASE_URL}"
  HEALTH_URL="${VITE_PROXY_TARGET:-}"
  if [[ -z "$HEALTH_URL" && -n "${E2E_API_BASE_URL:-}" ]]; then
    HEALTH_URL="${E2E_API_BASE_URL%/api/v1*}/health/"
  fi
  if [[ -z "$HEALTH_URL" ]]; then
    if curl -sf --connect-timeout 5 http://localhost:8000/health/ > /dev/null 2>&1; then
      export VITE_PROXY_TARGET=http://localhost:8000
      export E2E_API_BASE_URL="${E2E_API_BASE_URL:-http://localhost:8000/api/v1}"
    elif curl -s --connect-timeout 5 http://localhost:8001/health/ > /dev/null 2>&1; then
      export VITE_PROXY_TARGET=http://localhost:8001
      export E2E_API_BASE_URL="${E2E_API_BASE_URL:-http://localhost:8001/api/v1}"
      export E2E_WEB_PORT="${E2E_WEB_PORT:-5184}"
    else
      fail_no_backend
    fi
  else
    HEALTH_URL="${HEALTH_URL%/}/health/"
    if ! curl -sf --connect-timeout 5 "$HEALTH_URL" > /dev/null 2>&1; then
      fail_no_backend
    fi
  fi
  echo "✅ Backend API verified at ${VITE_PROXY_TARGET:-$E2E_API_BASE_URL}"
  exec npx playwright test "$@"
fi

# Auto-detect: try 8000 (dev) first, then 8001 (test stack)
# VITE_API_BASE_URL=/api/v1 + VITE_PROXY_TARGET: frontend uses proxy (avoids CORS)
# E2E_API_BASE_URL: full URL for Node-side fetch in fixtures
# --connect-timeout 5: fail fast if backend not running (avoids hanging for minutes)
echo "Checking backend API (ports 8000, 8001)..."
if curl -sf --connect-timeout 5 http://localhost:8000/health/ > /dev/null 2>&1; then
  export VITE_API_BASE_URL=/api/v1
  export VITE_PROXY_TARGET=http://localhost:8000
  export E2E_API_BASE_URL=http://localhost:8000/api/v1
  export PREFECT_INTEGRATION_SERVICE_URL="${PREFECT_INTEGRATION_SERVICE_URL:-http://localhost:8084}"
  echo "Detected API at port 8000 (docker-compose / docker-compose.dev)"
  # Reset auth rate limits so setup and tests can log in (avoids 429 after many runs)
  # Try hub-api (default) or hub-dev-api (docker-compose.dev)
  docker exec hub-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
  docker exec hub-api python hub/manage.py seed_default_plans 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py seed_default_plans 2>/dev/null || true
  docker exec hub-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
  docker exec hub-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || \
    docker exec hub-dev-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || true
elif curl -s --connect-timeout 5 http://localhost:8001/health/ > /dev/null 2>&1; then
  export VITE_API_BASE_URL=/api/v1
  export VITE_PROXY_TARGET=http://localhost:8001
  export E2E_API_BASE_URL=http://localhost:8001/api/v1
  # Local Vite on 5184 — must override FRONTEND_URL from .env (often :3010 for docker nginx)
  # so Playwright baseURL and webServer use the same port (see src/lib/playwright-frontend-resolve.ts).
  export E2E_WEB_PORT=5184
  export PREFECT_INTEGRATION_SERVICE_URL="${PREFECT_INTEGRATION_SERVICE_URL:-http://localhost:8114}"
  # ODBC E2E (phase6): API connects to postgres-test from inside container
  export E2E_POSTGRES_HOST="${E2E_POSTGRES_HOST:-postgres-test}"
  export E2E_POSTGRES_USER="${E2E_POSTGRES_USER:-hub_test}"
  export E2E_POSTGRES_PASSWORD="${E2E_POSTGRES_PASSWORD:-hub_test}"
  export E2E_POSTGRES_DB="${E2E_POSTGRES_DB:-hub_test_test_shared}"
  echo "Detected API at port 8001 (docker-compose.test)"
  REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
  # Ensure MailHog and worker-service for JOURNEY-AUTH-003 (password reset email delivery).
  # Always start worker-service when using test compose; worker processes send_password_reset_email jobs.
  # Start MailHog if not reachable; worker depends on it for SMTP.
  if ! curl -sf --connect-timeout 5 http://localhost:8025/api/v2/messages?limit=1 > /dev/null 2>&1; then
    echo "Starting MailHog and worker-service for password reset E2E..."
    docker compose -f "$REPO_ROOT/docker-compose.test.yml" up -d mailhog-test worker-service-test 2>/dev/null || true
    for i in $(seq 1 15); do
      if curl -sf --connect-timeout 5 http://localhost:8025/api/v2/messages?limit=1 > /dev/null 2>&1; then
        echo "MailHog ready at http://localhost:8025"
        break
      fi
      sleep 2
    done
  fi
  # Ensure worker-service is running (processes email jobs); may have been stopped or never started
  if ! curl -sf --connect-timeout 5 http://localhost:8087/healthz > /dev/null 2>&1; then
    echo "Starting worker-service for password reset E2E..."
    docker compose -f "$REPO_ROOT/docker-compose.test.yml" up -d worker-service-test 2>/dev/null || true
    for i in $(seq 1 15); do
      if curl -sf --connect-timeout 5 http://localhost:8087/healthz > /dev/null 2>&1; then
        echo "Worker service ready at http://localhost:8087"
        break
      fi
      sleep 2
    done
  fi
  # Ensure Prefect stack is running for scheduled export/ingestion journey tests
  if ! curl -sf --connect-timeout 5 http://localhost:8114/health > /dev/null 2>&1; then
    echo "Starting Prefect stack for scheduled export/ingestion tests..."
    docker compose -f "$REPO_ROOT/docker-compose.test.yml" up -d prefect-db-test prefect-server-test prefect-worker-test prefect-integration-service-test 2>/dev/null || true
    for i in $(seq 1 30); do
      if curl -sf --connect-timeout 5 http://localhost:8114/health > /dev/null 2>&1; then
        echo "Prefect integration service ready at http://localhost:8114"
        break
      fi
      sleep 2
    done
  fi
  # Restart API so storage presigned-URL fix (minio-test→localhost:9010 for browser) is applied.
  # Skip with E2E_SKIP_API_RESTART=1 when API is already stable (avoids socket hang up / ECONNREFUSED during tests).
  REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
  if [[ "${E2E_SKIP_API_RESTART:-0}" != "1" ]]; then
    echo "Restarting API service (may take 10–30s)..."
    docker compose -f "$REPO_ROOT/docker-compose.test.yml" restart api-service-test 2>/dev/null || true
  else
    echo "Skipping API restart (E2E_SKIP_API_RESTART=1)"
  fi
  API_READY=false
  for i in $(seq 1 30); do
    if curl -s --connect-timeout 5 http://localhost:8001/health/ > /dev/null 2>&1; then
      API_READY=true
      break
    fi
    sleep 2
  done
  if [[ "$API_READY" != "true" ]]; then
    echo "❌ Backend API at port 8001 did not become ready after restart (60s)."
    echo "Check: docker compose -f docker-compose.test.yml ps"
    echo "Logs:  docker compose -f docker-compose.test.yml logs api-service-test"
    exit 1
  fi
  # Settle time: frontend proxy may have stale connections after API restart; reduces ECONNRESET/socket hang up
  if [[ "${E2E_SKIP_API_RESTART:-0}" != "1" ]]; then
    echo "Waiting 30s for gunicorn workers and proxy connections to settle after API restart..."
    sleep 30
  fi
  # Reset auth rate limits so setup and tests can log in (avoids 429 after many runs)
  docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
  # Seed default plans so tenants can have subscriptions (required before ensure_e2e_user_roles assigns plans)
  docker exec hub-test-api python hub/manage.py seed_default_plans 2>/dev/null || true
  # Ensure E2E persona users exist with roles (DPO, DC, TA, PA, AUD, CPO)
  docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
  # Ensure E2E test tenants have active subscription (idempotent; no-op if user doesn't exist yet)
  docker exec hub-test-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || true

  # Start frontend dev server explicitly so Playwright has a reliable target.
  # Playwright's webServer with reuseExistingServer will reuse this if HTTP still answers.
  FRONTEND_STARTED=false
  ensure_e2e_frontend_dev_server "${E2E_WEB_PORT}" || exit 1
else
  fail_no_backend
fi

# Default to --project chromium when no --project is specified and E2E_VISIBLE is not set.
# Running all 3 projects (chromium + visible + chromium-routes) triples execution time
# since they run the same tests on the same browser. Use E2E_VISIBLE=1 to add the
# headed+slowMo visible project for interactive debugging.
HAS_PROJECT_ARG=false
for check_arg in "$@"; do
  if [[ "$check_arg" == --project=* ]] || [[ "$check_arg" == --project ]]; then
    HAS_PROJECT_ARG=true
    break
  fi
done

# Cap workers to 4 to reduce API/rate-limit pressure (5+ workers cause auth flakiness)
# Handles both --workers=5 and --workers 5 (space-separated)
ARGS=()
while [[ $# -gt 0 ]]; do
  arg="$1"
  shift
  if [[ "$arg" == --workers=* ]]; then
    w="${arg#--workers=}"
    if [[ "$w" =~ ^[0-9]+$ ]] && [[ "$w" -gt 4 ]]; then
      echo "⚠️  Capping workers from $w to 4 (reduces auth/rate-limit flakiness)"
      arg="--workers=4"
    fi
  elif [[ "$arg" == --workers ]] && [[ $# -gt 0 ]] && [[ "$1" =~ ^[0-9]+$ ]] && [[ "$1" -gt 4 ]]; then
    echo "⚠️  Capping workers from $1 to 4 (reduces auth/rate-limit flakiness)"
    shift
    arg="--workers=4"
  fi
  ARGS+=("$arg")
done

# Pre-flight: verify backend is still reachable before running tests
# Catches backend-down when reusing existing frontend or after API restart
# Use -s (not -f): 503 (unhealthy) still means API is reachable; only connection refused fails
API_ORIGIN="${VITE_PROXY_TARGET:-http://localhost:8000}"
if ! curl -s --connect-timeout 5 "${API_ORIGIN}/health/" > /dev/null 2>&1; then
  echo "❌ Backend API at ${API_ORIGIN} is not reachable (connection refused)."
  echo ""
  echo "If you have a frontend dev server running, it may be proxying to a stopped backend."
  echo "Stop the frontend (Ctrl+C) and ensure the backend is up before re-running:"
  echo "  docker compose -f docker-compose.test.yml up -d   # for port 8001"
  echo "  docker compose -f docker-compose.yml up -d       # for port 8000"
  fail_no_backend
fi
echo "Checking backend API availability at ${E2E_API_BASE_URL:-$API_ORIGIN/api/v1}..."
echo "✅ Backend API is available and responding"

# Vite may stop between the first curl and Playwright (OOM, strictPort conflict, user stopped dev server).
# Playwright webServer with reuseExistingServer does not restart a server that later disappears.
# Re-verify here so setup-auth never hits ERR_CONNECTION_REFUSED on a stale "already running".
if [[ -n "${E2E_WEB_PORT:-}" ]]; then
  if ! curl_frontend_root "${E2E_WEB_PORT}"; then
    echo "⚠️  Frontend on port ${E2E_WEB_PORT} not responding before Playwright; ensuring dev server..."
    ensure_e2e_frontend_dev_server "${E2E_WEB_PORT}" || exit 1
  fi
fi

# When no --project flag was passed, default to chromium only (avoids 3x test duplication).
# E2E_VISIBLE=1 adds the visible project; E2E_ALL_PROJECTS=1 runs all 3.
if [[ "$HAS_PROJECT_ARG" == "false" ]] && [[ "${E2E_ALL_PROJECTS:-0}" != "1" ]]; then
  if [[ "${E2E_VISIBLE:-0}" == "1" ]]; then
    ARGS+=(--project=chromium --project=visible)
  else
    ARGS+=(--project=chromium)
  fi
fi

# When we started the frontend, don't use exec so the EXIT trap runs to kill it
if [[ "${FRONTEND_STARTED:-false}" == "true" ]]; then
  npx playwright test "${ARGS[@]}"
else
  exec npx playwright test "${ARGS[@]}"
fi
