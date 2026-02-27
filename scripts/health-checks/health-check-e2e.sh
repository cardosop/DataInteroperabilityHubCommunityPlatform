#!/bin/bash
# Health Check Script - E2E Test Stack
# Checks core services required for E2E tests (backend and frontend).
# Uses docker-compose.test.yml service names and ports.
# See: docs/E2E_ENVIRONMENT_REQUIREMENTS.md
#
# Usage:
#   ./scripts/health-checks/health-check-e2e.sh
#   COMPOSE_FILE=docker-compose.test.yml ./scripts/health-checks/health-check-e2e.sh
#   ENVIRONMENT=test ./scripts/health-checks/health-check-e2e.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Force test stack compose file (must be set before sourcing health_check_lib)
export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
source "${SCRIPT_DIR}/health_check_lib.sh"
if [ ! -f "${COMPOSE_FILE}" ]; then
    log_error "Compose file not found: ${COMPOSE_FILE}. Run from project root."
    exit 1
fi

# Counters
TOTAL=0
PASSED=0
FAILED=0

main() {
    log_info "=========================================="
    log_info "Health Check - E2E Test Stack"
    log_info "=========================================="
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info ""
    
    # Core infrastructure (required for all E2E)
    log_info "--- Core Infrastructure ---"
    
    TOTAL=$((TOTAL + 1))
    if check_infrastructure_service "postgres-test" "pg_isready -U hub_test -d hub_test" "PostgreSQL (test)"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_infrastructure_service "redis-cache-test" "redis-cli ping" "Redis Cache (test)"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "minio-test" "9000/minio/health/live" "MinIO (test)"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Core application
    log_info "--- Core Application ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "api-service-test" "8000/health/" "API Service (test)"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Print summary
    print_summary "${TOTAL}" "${PASSED}" "${FAILED}"
}

# Run main function
main "$@"
