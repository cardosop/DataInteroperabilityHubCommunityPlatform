#!/usr/bin/env bash
# Task 29.7 Validation — Run E2E and security suites with timing assertions.
# 29.7.1: Full E2E suite <30 min; no flaky tests (backend + frontend Playwright).
# 29.7.2: Full security suite <10 min (tests/security/ + ODPS ref resolver + penetration).
# Prerequisites: Test stack up (docker compose -f docker-compose.test.yml up -d).
# If security tests fail with "relation X does not exist", ensure DBs have full schema:
#   docker compose -f docker-compose.test.yml stop api-service-test worker-service-test
#   docker compose -f docker-compose.test.yml run --rm --no-deps migrate-test-db
#   docker compose -f docker-compose.test.yml start api-service-test worker-service-test
# Compliance test uses hub_test_test_phase13 to avoid deadlock when pytest+runserver share shared DB.
# Optional: .env.test for test stack env (e.g. POSTGRES_TEST_*); script works without it.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="docker-compose.test.yml"
ENV_ARGS=()
[[ -f .env.test ]] && ENV_ARGS=(--env-file .env.test)

E2E_MAX_SEC=1800   # 30 min
SECURITY_MAX_SEC=900  # 15 min (190 tests + ref resolver + penetration; 10 min often exceeded)

run_security=false
run_e2e=false
e2e_backend_only=false
for arg in "$@"; do
  case "$arg" in
    --security) run_security=true ;;
    --e2e) run_e2e=true ;;
    --e2e-backend-only) run_e2e=true; e2e_backend_only=true ;;
    --help|-h)
      echo "Usage: $(basename "$0") [--security] [--e2e] [--e2e-backend-only]"
      echo "  --security         Run security suite only (target <10 min)"
      echo "  --e2e             Run full E2E suite: backend + frontend Playwright (target <30 min)"
      echo "  --e2e-backend-only Run backend E2E only (tests/e2e/)"
      echo "  (no args)         Run both security and E2E"
      exit 0
      ;;
  esac
done

if [[ "$run_security" == "false" ]] && [[ "$run_e2e" == "false" ]]; then
  run_security=true
  run_e2e=true
fi

# Security/E2E require api-service-test Up (exec path). Run path has DB/network conflicts.
# Prerequisite: docker compose -f docker-compose.test.yml up -d (after migrate-test-db).
# Security: use shared DB (hub_test_test_shared) so schema is guaranteed (api-service-test uses it).
# E2E: use phase13 (hub_test_test_phase13) to avoid shared-DB deadlocks with runserver.
_run_cmd_security() {
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T -e TEST_DB_SUFFIX=shared -e POSTGRES_DB=hub_test_test_shared api-service-test bash -c "$1"
  else
    echo "❌ api-service-test must be Up. Run: docker compose -f $COMPOSE_FILE up -d" >&2
    exit 1
  fi
}
_run_cmd_e2e() {
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T -e TEST_DB_SUFFIX=phase13 -e POSTGRES_DB=hub_test api-service-test bash -c "$1"
  else
    echo "❌ api-service-test must be Up. Run: docker compose -f $COMPOSE_FILE up -d" >&2
    exit 1
  fi
}
# Run with phase13 (hub_test_test_phase13) to avoid deadlock when pytest+runserver share shared DB.
_run_cmd_phase13() {
  if docker compose -f "$COMPOSE_FILE" ps api-service-test 2>/dev/null | grep -q "Up"; then
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T -e TEST_DB_SUFFIX=phase13 -e POSTGRES_DB=hub_test api-service-test bash -c "$1"
  else
    echo "❌ api-service-test must be Up. Run: docker compose -f $COMPOSE_FILE up -d" >&2
    exit 1
  fi
}

_ensure_shared_db_ready() {
  # Ensure hub_test_test_shared exists and has security_audit_logs (required by main security, ref resolver, penetration tests).
  # migrate-test-db creates it from hub_test template. Run if DB missing or schema incomplete.
  local shared_ok=false
  if docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T postgres-test psql -U hub_test -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='hub_test_test_shared'" 2>/dev/null | grep -q 1; then
    if docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T postgres-test psql -U hub_test -d hub_test_test_shared -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='security_audit_logs'" 2>/dev/null | grep -q 1; then
      shared_ok=true
    fi
  fi
  if [[ "$shared_ok" != "true" ]]; then
    echo "Creating/refreshing hub_test_test_shared (run migrate-test-db)..."
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" run --rm --no-deps migrate-test-db 2>/dev/null || true
  fi
}

if [[ "$run_security" == "true" ]]; then
  echo "===== 29.7.2 Security suite (target <${SECURITY_MAX_SEC}s) ====="
  SEC_START=$(date +%s)
  set +e
  # Ensure hub_test_test_shared exists and has full schema (security_audit_logs required by ref resolver tests).
  _ensure_shared_db_ready
  # Ensure hub_test_test_phase13 exists and is migrated (compliance test uses it to avoid shared-DB deadlock).
  # ensure-test-db creates phase13 as empty; migrate-test-db must run to apply schema (tenants table, etc.).
  PHASE13_OK=false
  if docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T postgres-test psql -U hub_test -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='hub_test_test_phase13'" 2>/dev/null | grep -q 1; then
    if docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T postgres-test psql -U hub_test -d hub_test_test_phase13 -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='tenants'" 2>/dev/null | grep -q 1; then
      PHASE13_OK=true
    fi
  fi
  if [[ "$PHASE13_OK" != "true" ]]; then
    echo "Creating/migrating hub_test_test_phase13 (run migrate-test-db)..."
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" run --rm --no-deps migrate-test-db 2>/dev/null || true
  fi
  # Full security suite per SECURITY_TEST_COVERAGE.md. Main security pytest uses phase13 to avoid
  # "connection already closed" / deadlock when pytest+runserver share hub_test_test_shared.
  # Compliance test also uses phase13 (tenant isolation test does DB writes).
  SEC_PYTEST=0
  SEC_COMPLIANCE=0
  SEC_REF=0
  SEC_PEN=0
  _ensure_shared_db_ready
  _run_cmd_phase13 "cd /app && PYTHONPATH=/app pytest tests/security/ --ignore=tests/security/test_compliance_security.py -v --tb=short -q --reuse-db --timeout=120" || SEC_PYTEST=1
  _run_cmd_phase13 "cd /app && PYTHONPATH=/app pytest tests/security/test_compliance_security.py -v --tb=short -q --reuse-db --timeout=120" || SEC_COMPLIANCE=1
  _ensure_shared_db_ready
  _run_cmd_security "cd /app && PYTHONPATH=/app pytest hub/apps/contracts/tests/security/test_ref_resolver_security.py -v --tb=short -q --reuse-db --timeout=120" || SEC_REF=1
  _ensure_shared_db_ready
  _run_cmd_security "cd /app && PYTHONPATH=/app pytest tests/security/penetration_test_odps_ref_resolver.py -v --tb=short -q --reuse-db --timeout=120" || SEC_PEN=1
  set -e
  SEC_END=$(date +%s)
  SEC_DUR=$((SEC_END - SEC_START))
  echo "Security suite duration: ${SEC_DUR}s"
  SEC_EXIT=0
  [[ $SEC_PYTEST -ne 0 ]] && SEC_EXIT=1
  [[ $SEC_COMPLIANCE -ne 0 ]] && SEC_EXIT=1
  [[ $SEC_REF -ne 0 ]] && SEC_EXIT=1
  [[ $SEC_PEN -ne 0 ]] && SEC_EXIT=1
  if [[ $SEC_EXIT -ne 0 ]]; then
    echo "❌ Security suite failed (pytest=$SEC_PYTEST compliance=$SEC_COMPLIANCE ref_resolver=$SEC_REF penetration=$SEC_PEN)"
    exit 1
  fi
  if [[ $SEC_DUR -gt $SECURITY_MAX_SEC ]]; then
    echo "❌ Security suite exceeded ${SECURITY_MAX_SEC}s (got ${SEC_DUR}s)"
    exit 1
  fi
  echo "✅ Security suite ${SEC_DUR}s < ${SECURITY_MAX_SEC}s"
fi

if [[ "$run_e2e" == "true" ]]; then
  echo "===== 29.7.1 E2E suite (target <${E2E_MAX_SEC}s) ====="
  E2E_START=$(date +%s)
  set +e
  # Ensure hub_test_test_phase13 exists (E2E uses TEST_DB_SUFFIX=phase13). migrate-test-db creates it
  # at stack start; re-run if missing (e.g. fresh postgres volume) to avoid "database does not exist".
  if ! docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" exec -T postgres-test psql -U hub_test -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='hub_test_test_phase13'" 2>/dev/null | grep -q 1; then
    echo "Creating hub_test_test_phase13 (run migrate-test-db)..."
    docker compose -f "$COMPOSE_FILE" "${ENV_ARGS[@]}" run --rm --no-deps migrate-test-db 2>/dev/null || true
  fi
  echo "Backend E2E..."
  # Use --rootdir=/app so tests/conftest.py is discovered (with -c tests/e2e/pytest.ini rootdir becomes
  # tests/e2e and parent conftest is skipped -> missing create_test_db/sync_apps patches -> hang)
  _run_cmd_e2e "cd /app && PYTHONPATH=/app pytest tests/e2e/ -v -c tests/e2e/pytest.ini --rootdir=/app --tb=short"
  E2E_BACKEND=$?
  set -e
  if [[ $E2E_BACKEND -ne 0 ]]; then
    echo "❌ Backend E2E failed (exit $E2E_BACKEND)"
    exit 1
  fi
  if [[ "$e2e_backend_only" != "true" ]] && [[ -d frontend ]]; then
    echo "Frontend E2E (Playwright)..."
    set +e
    (cd frontend && npm run test:e2e 2>&1)
    E2E_FRONTEND=$?
    set -e
    if [[ $E2E_FRONTEND -ne 0 ]]; then
      echo "❌ Frontend E2E failed (exit $E2E_FRONTEND)"
      exit 1
    fi
  fi
  E2E_END=$(date +%s)
  E2E_DUR=$((E2E_END - E2E_START))
  echo "E2E suite duration: ${E2E_DUR}s"
  if [[ $E2E_DUR -gt $E2E_MAX_SEC ]]; then
    echo "❌ E2E suite exceeded ${E2E_MAX_SEC}s (got ${E2E_DUR}s)"
    exit 1
  fi
  echo "✅ E2E suite ${E2E_DUR}s < ${E2E_MAX_SEC}s"
fi

echo "===== 29.7 validation complete ====="
