#!/bin/bash
# Health Check Script - Workflow Services
# Checks health of workflow-related services

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/health_check_lib.sh"

# Detect compose file
detect_compose_file

# Counters
TOTAL=0
PASSED=0
FAILED=0

main() {
    log_info "=========================================="
    log_info "Health Check - Workflow Services"
    log_info "=========================================="
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info ""
    
    # Workflow Engine Service
    TOTAL=$((TOTAL + 1))
    if check_service_health "workflow-engine-service" "8088/healthz" "Workflow Engine Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Workflow Registry Service
    TOTAL=$((TOTAL + 1))
    if check_service_health "workflow-registry-service" "8089/health" "Workflow Registry Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Dependencies
    log_info ""
    log_info "--- Dependencies ---"
    
    TOTAL=$((TOTAL + 1))
    if check_infrastructure_service "postgres" "pg_isready -U hub" "PostgreSQL"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_infrastructure_service "redis" "redis-cli ping" "Redis"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Print summary
    print_summary "${TOTAL}" "${PASSED}" "${FAILED}"
}

# Run main function
main "$@"

