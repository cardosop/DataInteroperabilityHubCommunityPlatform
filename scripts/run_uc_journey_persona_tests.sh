#!/usr/bin/env bash
# Run UC/journey/persona E2E tests (Task 6.7.3)
# Selector: -m uc_journey_persona (equivalent to -m "uc or journey or persona")
# Writes logs/JUnit to test_reports_comprehensive/{DATE}/uc_journey_persona/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
export COMPOSE_FILE

if [[ -n "${API_SERVICE_NAME:-}" ]]; then
  API_SVC="${API_SERVICE_NAME}"
elif [[ "${COMPOSE_FILE:-}" == *"docker-compose.test"* ]]; then
  API_SVC="api-service-test"
else
  API_SVC="api-service"
fi

DATE="${DATE:-$(date +%Y-%m-%d)}"
REPORT_DIR="test_reports_comprehensive/${DATE}/uc_journey_persona"
mkdir -p "${REPORT_DIR}"

export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="${PROJECT_DIR}"

# Batch mode: set UC_JOURNEY_PERSONA_BATCH=persona|uc|journey to reduce memory (exit 137)
MARKER="${UC_JOURNEY_PERSONA_BATCH:-uc_journey_persona}"

echo "===== UC/Journey/Persona E2E tests ====="
echo "Selector: -m ${MARKER}"
echo "Artifacts: ${REPORT_DIR}"
echo ""

START=$(date +%s)
set +e  # Allow pytest to fail without exiting script
if docker compose exec -T "${API_SVC}" true 2>/dev/null; then
  echo "Running inside Docker (${API_SVC})..."
  PYTEST_DOCKER_COMPOSE_RUNTIME=1 docker compose exec -T "${API_SVC}" bash -c \
    "cd /app && PYTHONPATH=/app DJANGO_SETTINGS_MODULE=hub.settings python -m pytest tests/e2e/ -v -m ${MARKER} --reuse-db --timeout=900 --junit-xml=/tmp/junit_uc_journey_persona.xml --tb=short" \
    2>&1 | tee "${REPORT_DIR}/uc_journey_persona.log"
  EXIT_CODE=${PIPESTATUS[0]}
  docker compose cp "${API_SVC}:/tmp/junit_uc_journey_persona.xml" "${REPORT_DIR}/junit.xml" 2>/dev/null || true
  if [[ $EXIT_CODE -eq 137 ]]; then
    echo ""
    echo "Exit 137 (SIGKILL) - likely OOM. Try running in smaller batches:"
    echo "  UC_JOURNEY_PERSONA_BATCH=persona $0   # persona only"
    echo "  UC_JOURNEY_PERSONA_BATCH=uc $0       # uc only"
    echo "  UC_JOURNEY_PERSONA_BATCH=journey $0  # journey only"
  fi
else
  echo "Running without Docker (API service not running)..."
  # Prefer project venv (has Django, pytest-django, etc.)
  if [[ -z "${PYTHON:-}" ]]; then
    for venv_py in "${PROJECT_DIR}/venv/bin/python" "${PROJECT_DIR}/venv/bin/python3" \
                   "${PROJECT_DIR}/.venv/bin/python" "${PROJECT_DIR}/.venv/bin/python3" \
                   "${PROJECT_DIR}/venv-python312-test/bin/python" "${PROJECT_DIR}/venv-python312-test/bin/python3"; do
      if [[ -x "$venv_py" ]]; then
        PYTHON="$venv_py"
        echo "Using venv: $PYTHON"
        break
      fi
    done
  fi
  if [[ -z "${PYTHON:-}" ]]; then
    PYTHON="$(command -v python3 || command -v python)"
  fi
  if [[ -z "${PYTHON:-}" ]]; then
    echo "Error: python3 or python not found in PATH"
    exit 1
  fi
  # Verify Django is available (required for tests)
  if ! "${PYTHON}" -c "import django" 2>/dev/null; then
    echo "Error: Django not installed. UC/journey/persona tests require the project environment."
    echo "  Option 1 (recommended): Run with Docker: docker compose -f ${COMPOSE_FILE} up -d api-service-test && $0"
    echo "  Option 2: Create venv and install deps: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt -r requirements-dev.txt"
    exit 1
  fi
  # Override DB host for host-side runs: .env uses 'postgres' (Docker hostname) which doesn't resolve outside containers.
  # Use localhost + test port so we can connect to postgres-test container when it's running (even if api-service-test failed).
  export POSTGRES_HOST="${POSTGRES_HOST:-localhost}"
  export POSTGRES_PORT="${POSTGRES_PORT:-5434}"
  export POSTGRES_USER="${POSTGRES_USER:-hub_test}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-hub_test}"
  export POSTGRES_DB="${POSTGRES_DB:-hub_test}"
  # Try with --reuse-db --timeout (require pytest-django, pytest-timeout); fallback if not installed
  PYTEST_DOCKER_COMPOSE_RUNTIME=1 "${PYTHON}" -m pytest tests/e2e/ -v -m "${MARKER}" \
    --reuse-db --timeout=900 --junit-xml="${REPORT_DIR}/junit.xml" --tb=short \
    2>&1 | tee "${REPORT_DIR}/uc_journey_persona.log"
  EXIT_CODE=${PIPESTATUS[0]}
  if [[ $EXIT_CODE -eq 4 ]]; then
    echo "Retrying without --reuse-db --timeout (install requirements-dev.txt for full support)..."
    PYTEST_DOCKER_COMPOSE_RUNTIME=1 "${PYTHON}" -m pytest tests/e2e/ -v -m "${MARKER}" \
      --junit-xml="${REPORT_DIR}/junit.xml" --tb=short \
      2>&1 | tee "${REPORT_DIR}/uc_journey_persona.log"
    EXIT_CODE=${PIPESTATUS[0]}
  fi
fi
set -e
END=$(date +%s)

echo "UC_JOURNEY_PERSONA_EXIT=${EXIT_CODE}" >> "${REPORT_DIR}/uc_journey_persona.log"
echo "UC_JOURNEY_PERSONA_DURATION=$((END - START))" >> "${REPORT_DIR}/uc_journey_persona.log"

echo ""
echo "===== UC/Journey/Persona tests complete (exit ${EXIT_CODE}) ====="
echo "Evidence: ${REPORT_DIR}"
exit $EXIT_CODE
