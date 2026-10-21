#!/bin/bash
# Health Check Script - Event Bus Services
# Checks health of event bus-related services

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
    log_info "Health Check - Event Bus Services"
    log_info "=========================================="
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info ""
    
    # Event Bus Health Service
    TOTAL=$((TOTAL + 1))
    if check_service_health "event-bus-health-service" "8090/healthz" "Event Bus Health Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Event Schema Registry Service
    TOTAL=$((TOTAL + 1))
    if check_service_health "event-schema-registry-service" "8091/health" "Event Schema Registry Service"; then
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

