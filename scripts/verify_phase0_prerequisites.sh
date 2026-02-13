#!/usr/bin/env bash
# Phase 0 — Prerequisites and Environment Verification
# Implements tasks 0.1, 0.2, 0.3 from testsfix1/tasks.md.
# No mocks/stubs; real Docker and real service health checks.
# Usage: from repo root, ./scripts/verify_phase0_prerequisites.sh [--no-up]
#   --no-up: skip bringing up the stack (only validate config and check already-running services)

set -euo pipefail

if [[ -z "${BASH_VERSION:-}" ]]; then
  exec /usr/bin/env bash "$0" "$@"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
ENV_FILE="${ENV_FILE:-.env.test}"
# Core test services (must match scripts/run_phase_12a_batched.sh)
CORE_SERVICES=(
  postgres-test
  redis-cache-test
  redis-queue-test
  redis-events-test
  redis-channels-test
  minio-test
  fuseki-test
  datacontract-service-test
  dq-service-test
  compliance-service-test
  semantic-service-test
  api-service-test
)

run_compose() {
  local extra=()
  if [[ -f "$ENV_FILE" ]]; then
    extra+=(--env-file "$ENV_FILE")
  fi
  docker compose -f "$COMPOSE_FILE" "${extra[@]}" "$@"
}

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

ok() {
  echo "OK: $*"
}

# ---- 0.1 Docker, Docker Compose, compose file, stack can be brought up ----
check_0_1() {
  echo "--- Phase 0.1: Docker, Compose, and stack ---"

  if ! command -v docker &>/dev/null; then
    fail "Docker is not available (docker not in PATH)."
  fi
  ok "Docker available: $(docker --version)"

  if ! docker compose version &>/dev/null; then
    if ! docker-compose version &>/dev/null 2>/dev/null; then
      fail "Docker Compose is not available (docker compose or docker-compose not in PATH)."
    fi
    ok "Docker Compose available (docker-compose): $(docker-compose version --short 2>/dev/null || docker-compose version)"
  else
    ok "Docker Compose available: $(docker compose version --short 2>/dev/null || docker compose version)"
  fi

  if [[ ! -f "$COMPOSE_FILE" ]]; then
    fail "Compose file not found: $COMPOSE_FILE"
  fi
  ok "Compose file present: $COMPOSE_FILE"

  if ! run_compose config --quiet 2>/dev/null; then
    fail "Compose file is invalid: $COMPOSE_FILE (run: docker compose -f $COMPOSE_FILE config)"
  fi
  ok "Compose file is valid"

  if [[ "${1:-}" == "--no-up" ]]; then
    ok "Skipping stack bring-up (--no-up)"
  else
    echo "Bringing up test stack (docker compose up -d)..."
    if ! run_compose up -d 2>&1; then
      fail "Stack bring-up failed (docker compose -f $COMPOSE_FILE up -d). Fix the cause and re-run."
    fi
    ok "Stack brought up (up -d); Phase 0.2 will wait for core services to become healthy."
  fi
}

# ---- 0.2 Core test services start and are healthy ----
# Uses docker inspect for reliable health status (works with all Compose versions).
service_health_status() {
  local svc="$1"
  local cid
  cid=$(run_compose ps -q "$svc" 2>/dev/null | head -1)
  if [[ -z "$cid" ]]; then
    echo "missing"
    return
  fi
  local state
  state=$(docker inspect -f '{{.State.Status}}' "$cid" 2>/dev/null || echo "unknown")
  if [[ "$state" != "running" ]]; then
    echo "$state"
    return
  fi
  local health
  health=$(docker inspect -f '{{.State.Health.Status}}' "$cid" 2>/dev/null || echo "none")
  if [[ "$health" == "healthy" ]]; then
    echo "healthy"
  elif [[ "$health" == "none" ]] || [[ -z "$health" ]]; then
    echo "running"
  else
    echo "$health"
  fi
}

check_0_2() {
  echo "--- Phase 0.2: Core test services healthy ---"
  local wait_max="${PHASE0_WAIT_MAX:-300}"
  local waited=0
  local interval=10

  while [[ $waited -lt $wait_max ]]; do
    local all_healthy=true
    for svc in "${CORE_SERVICES[@]}"; do
      local status
      status=$(service_health_status "$svc")
      if [[ "$status" != "healthy" ]]; then
        all_healthy=false
        echo "  Waiting for $svc (current: $status)..."
        break
      fi
    done
    if [[ "$all_healthy" == "true" ]]; then
      for svc in "${CORE_SERVICES[@]}"; do
        ok "Service healthy: $svc"
      done
      return 0
    fi
    sleep "$interval"
    waited=$((waited + interval))
  done

  echo "Service status after ${wait_max}s:"
  for svc in "${CORE_SERVICES[@]}"; do
    echo "  $svc: $(service_health_status "$svc")"
  done
  fail "Not all core services became healthy within ${wait_max}s. Check: run_compose ps -a"
}

# ---- 0.3 DJANGO_SETTINGS_MODULE, PYTHONPATH, pytest.ini, tests/conftest.py ----
check_0_3() {
  echo "--- Phase 0.3: Django and pytest configuration ---"

  if [[ ! -f pytest.ini ]]; then
    fail "pytest.ini not found in repo root."
  fi
  ok "pytest.ini present"

  if ! grep -q 'DJANGO_SETTINGS_MODULE' pytest.ini; then
    fail "pytest.ini does not set DJANGO_SETTINGS_MODULE (expected: hub.settings)."
  fi
  if ! grep -q 'hub\.settings' pytest.ini; then
    fail "pytest.ini does not set DJANGO_SETTINGS_MODULE=hub.settings."
  fi
  ok "pytest.ini sets DJANGO_SETTINGS_MODULE=hub.settings"

  if [[ ! -f tests/conftest.py ]]; then
    fail "tests/conftest.py not found."
  fi
  ok "tests/conftest.py present"

  # PYTHONPATH: verify when set; require repo root to be on path for test runs
  local norm_root
  norm_root="$(cd "$PROJECT_DIR" && pwd)"
  if [[ -n "${PYTHONPATH:-}" ]]; then
    local found=false
    IFS=: read -ra pp_paths <<< "$PYTHONPATH"
    for p in "${pp_paths[@]}"; do
      [[ -z "${p:-}" ]] && continue
      local norm_p
      norm_p="$(cd "$p" 2>/dev/null && pwd)" || continue
      if [[ "$norm_p" == "$norm_root" ]]; then
        found=true
        break
      fi
    done
    if [[ "$found" != "true" ]]; then
      echo "  WARNING: PYTHONPATH is set but does not contain repo root ($norm_root). Pytest should be run with PYTHONPATH including repo root." >&2
    else
      ok "PYTHONPATH contains repo root"
    fi
  else
    echo "  NOTE: PYTHONPATH not set; for pytest runs set PYTHONPATH from repo root (e.g. PYTHONPATH=\$PWD or /app in container)." >&2
  fi
  ok "Phase 0.3 checks passed"
}

# ---- Main ----
NO_UP=""
for arg in "$@"; do
  case "$arg" in
    --no-up) NO_UP=--no-up ;;
    --help|-h)
      echo "Usage: $0 [--no-up] [--help]"
      echo "  --no-up   Skip bringing up the stack; still run health check (0.2) and config (0.3)."
      echo "  --help    Show this help."
      exit 0
      ;;
  esac
done

echo "=========================================="
echo "Phase 0 — Prerequisites and Environment"
echo "=========================================="
echo ""

check_0_1 $NO_UP

# Always run 0.2 when we need full verification; --no-up only skips bring-up, not health check
check_0_2

check_0_3

echo ""
echo "=========================================="
echo "Phase 0 verification passed."
echo "=========================================="
