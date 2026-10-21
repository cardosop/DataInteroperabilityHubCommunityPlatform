#!/usr/bin/env bash
# Auto-detect backend API port (8000 = dev compose, 8001 = test compose) and run E2E.
# Use when backend is already running. No mocks/stubs.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

# Concurrent-run guard: a parallel invocation of this wrapper restarts the
# shared API container and mutates shared DB state (auth rate-limit resets,
# plan/user seeding) — mid-batch that tears the running tests. Observed in
# batch b7: a parallel single-spec run restarted api-service-test while the
# batch was mid-flight and produced NETWORK_ERROR storms / 120s timeouts in
# three subsequent specs. The PID file also survives the `exec npx playwright`
# fast-path below (exec keeps the PID), so the lock tracks the real run
# lifetime; a stale file (dead PID) is silently taken over.
# E2E_FORCE_PARALLEL=1 overrides for explicitly coordinated runs.
E2E_LOCKFILE="${TMPDIR:-/tmp}/dih-e2e-batch.pid"
if [[ "${E2E_FORCE_PARALLEL:-0}" != "1" ]]; then
  if [[ -f "$E2E_LOCKFILE" ]] && kill -0 "$(cat "$E2E_LOCKFILE" 2>/dev/null)" 2>/dev/null; then
    echo "❌ Another E2E run (PID $(cat "$E2E_LOCKFILE")) is in progress on this stack."
    echo "   A parallel run would restart the shared API and corrupt the in-flight batch."
    echo "   Wait for it to finish, or set E2E_FORCE_PARALLEL=1 to override."
    exit 1
  fi
  echo "$$" > "$E2E_LOCKFILE"
fi

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

# Per-invocation PID file ($$ suffix) + shared log file for the supervised
# dev server. The PID file is the ownership marker: the EXIT trap only kills
# a server THIS invocation started (or restarted via the watchdog) — a reused
# pre-existing server is left alone, and concurrent runs on the same port
# each kill only their own process group (a shared PID file let run A's exit
# trap kill run B's restarted server).
frontend_pid_file() { echo "${TMPDIR:-/tmp}/dih-e2e-frontend-${1}-$$.pid"; }
frontend_log_file() { echo "${TMPDIR:-/tmp}/dih-e2e-frontend-${1}.log"; }

# Start npm run dev on port as its own session/process-group leader and
# wait until HTTP answers. The whole tree (npm wrapper + vite) is killed
# later via the process group — killing only the npm wrapper PID left
# orphaned vites holding the port (stale-server drift across runs).
start_frontend_server() {
  local port="${1:?}"
  local pid_file log_file pid i
  pid_file="$(frontend_pid_file "$port")"
  log_file="$(frontend_log_file "$port")"
  VITE_WS_ENABLED=false VITE_E2E_TEST=true setsid npm run dev -- --port "${port}" --strictPort \
    > "$log_file" 2>&1 &
  pid=$!
  echo "$pid" > "$pid_file"
  for i in $(seq 1 60); do
    if curl_frontend_root "$port"; then
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "❌ Frontend process exited unexpectedly before becoming ready."
      echo "   Check: ${log_file} (strictPort fails if the port is held by a stale process)"
      rm -f "$pid_file"
      return 1
    fi
    sleep 2
  done
  echo "❌ Frontend failed to become ready within ~120s"
  kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  rm -f "$pid_file"
  return 1
}

# Kill the supervised dev server (whole process group) when this script
# owns one. No-op when no PID file exists (server was reused).
stop_frontend_server() {
  local port="${1:?}"
  local pid_file pid
  pid_file="$(frontend_pid_file "$port")"
  [[ -f "$pid_file" ]] || return 0
  pid="$(cat "$pid_file" 2>/dev/null || true)"
  rm -f "$pid_file"
  [[ -n "$pid" ]] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  kill -- -"$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
}

# Start npm run dev on port if nothing is listening; wait until HTTP answers.
ensure_e2e_frontend_dev_server() {
  local port="${1:?}"
  if curl_frontend_root "$port"; then
    echo "Frontend already running at http://localhost:${port}"
    return 0
  fi
  echo "Starting frontend dev server on port ${port}..."
  start_frontend_server "$port" || return 1
  echo "Frontend ready at http://localhost:${port}"
}

# Mid-run supervisor. Playwright's webServer (reuseExistingServer) never
# restarts a dev server that dies AFTER the run started — OOM, a vite
# dependency re-optimization restart window, or a concurrent run's cleanup
# killing the shared port all turn into cascading ERR_CONNECTION_REFUSED
# with nothing to recover them. Poll the port while playwright runs; when
# it stays down for two consecutive polls (~6s), start a fresh server so
# later tests recover. Bounded restarts avoid a crash-loop on a port that
# can never come up.
watchdog_frontend() {
  local port="${1:?}"
  local misses=0 restarts=0
  while kill -0 "$PLAYWRIGHT_PID" 2>/dev/null; do
    sleep 3
    if curl_frontend_root "$port"; then
      misses=0
    else
      misses=$((misses + 1))
      if (( misses >= 2 )); then
        misses=0
        if (( restarts >= 3 )); then
          echo "❌ Frontend restarted ${restarts} times and is still failing; giving up supervision (tests will surface connection errors)"
          return 1
        fi
        echo "⚠️  Frontend on port ${port} went down mid-run; restarting (${restarts}/3)…"
        if start_frontend_server "$port"; then
          restarts=$((restarts + 1))
        else
          echo "❌ Frontend restart failed; will retry next cycle"
        fi
      fi
    fi
  done
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
  export E2E_WEB_PORT="${E2E_WEB_PORT:-5184}"
  # Ownership cleanup: kill the supervised dev server on exit ONLY when this
  # script started/restarted it (PID file present). Reused servers are left
  # untouched for any concurrent run still using them.
  trap 'stop_frontend_server "${E2E_WEB_PORT}"' EXIT
  export PREFECT_INTEGRATION_SERVICE_URL="${PREFECT_INTEGRATION_SERVICE_URL:-http://localhost:8114}"
  # ODBC E2E (phase6): API connects to postgres-test from inside container
  export E2E_POSTGRES_HOST="${E2E_POSTGRES_HOST:-postgres-test}"
  export E2E_POSTGRES_USER="${E2E_POSTGRES_USER:-hub_test}"
  export E2E_POSTGRES_PASSWORD="${E2E_POSTGRES_PASSWORD:-hub_test}"
  export E2E_POSTGRES_DB="${E2E_POSTGRES_DB:-hub_test_test_shared}"
  echo "Detected API at port 8001 (docker-compose.test)"
  # The test stack ships Stripe test-mode keys (docker-compose.test.yml
  # defaults) — enable the Stripe checkout E2E on this stack instead of
  # leaving it permanently skipped. Staging/CI still opt in explicitly.
  export E2E_MARKETPLACE_STRIPE="${E2E_MARKETPLACE_STRIPE:-1}"
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
  # Recreate the API container so the current compose env is applied (e.g.
  # GUNICORN_MAX_REQUESTS=0, which stops the single-worker recycle cycle that
  # killed in-flight connections every ~15-30 min mid-batch — batch-7's
  # NETWORK_ERROR storm root cause). `docker compose restart` only restarts
  # the PROCESS with the OLD env: env changes in docker-compose.test.yml
  # never reach a stale container, and the recycling keeps happening no
  # matter how many times the wrapper restarts it. `up -d --force-recreate`
  # rebuilds the container with current compose config (env + code paths).
  # Skip with E2E_SKIP_API_RESTART=1 when the API is known-good (avoids the
  # recreate + settle window during repeated single-spec runs).
  REPO_ROOT="$(cd "$FRONTEND_DIR/.." && pwd)"
  if [[ "${E2E_SKIP_API_RESTART:-0}" != "1" ]]; then
    echo "Recreating API service with current compose env (may take 10–30s)..."
    docker compose -f "$REPO_ROOT/docker-compose.test.yml" up -d --force-recreate api-service-test 2>/dev/null || true
  else
    echo "Skipping API recreate (E2E_SKIP_API_RESTART=1)"
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
  # Worker warm-up probe: /health/ goes green as soon as the gunicorn MASTER
  # is up, while workers are still importing Django (per-worker app init +
  # ref-warming thread — 30s+ on the HDD dev box). Requests that land on
  # booting workers fail or stall, which surfaces as the batch-start
  # NETWORK_ERROR / timeout storms. Probe a worker-backed endpoint (OpenAPI
  # schema needs a fully-booted worker + DB) until it answers, bounded.
  WARM_READY=false
  for i in $(seq 1 30); do
    if curl -sf --connect-timeout 10 --max-time 30 http://localhost:8001/api/v1/openapi.json > /dev/null 2>&1; then
      WARM_READY=true
      break
    fi
    sleep 3
  done
  if [[ "$WARM_READY" != "true" ]]; then
    echo "⚠️ API workers not warm after ~90s — continuing anyway (tests have their own retries)"
  fi
  # Reset auth rate limits so setup and tests can log in (avoids 429 after many runs)
  # Try both legacy `hub-test-api` and current `hub-test-api-mvp` container names
  # (test stack was renamed when the MVP-mode build replaced the dual container layout).
  docker exec hub-test-api python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || \
    docker exec hub-test-api-mvp python hub/manage.py reset_e2e_auth_rate_limits 2>/dev/null || true
  # Seed default plans so tenants can have subscriptions (required before ensure_e2e_user_roles assigns plans)
  docker exec hub-test-api python hub/manage.py seed_default_plans 2>/dev/null || \
    docker exec hub-test-api-mvp python hub/manage.py seed_default_plans 2>/dev/null || true
  # Ensure E2E persona users exist with roles (DPO, DC, TA, PA, AUD, CPO)
  docker exec hub-test-api python hub/manage.py ensure_e2e_user_roles 2>/dev/null || \
    docker exec hub-test-api-mvp python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
  # Ensure E2E test tenants have active subscription (idempotent; no-op if user doesn't exist yet)
  docker exec hub-test-api python hub/manage.py ensure_e2e_subscription 2>/dev/null || \
    docker exec hub-test-api-mvp python hub/manage.py ensure_e2e_subscription 2>/dev/null || true

  # Start frontend dev server explicitly so Playwright has a reliable target.
  # Playwright's webServer with reuseExistingServer will reuse this if HTTP still answers.
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

# Supervised run (no exec) when an explicit E2E web port is in play: the
# watchdog keeps the dev server alive mid-run and the EXIT trap kills the
# process group this script owns. Without a known port, keep the exec
# fast-path (Playwright's own webServer manages the frontend there).
if [[ -n "${E2E_WEB_PORT:-}" ]]; then
  npx playwright test "${ARGS[@]}" &
  PLAYWRIGHT_PID=$!
  watchdog_frontend "${E2E_WEB_PORT}" &
  WATCHDOG_PID=$!
  set +e
  wait "$PLAYWRIGHT_PID"
  PW_STATUS=$?
  set -e
  kill "$WATCHDOG_PID" 2>/dev/null || true
  wait "$WATCHDOG_PID" 2>/dev/null || true
  exit "$PW_STATUS"
fi

exec npx playwright test "${ARGS[@]}"
