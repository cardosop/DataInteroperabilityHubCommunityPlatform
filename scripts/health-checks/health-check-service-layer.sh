#!/bin/bash
# Health Check Script - Service Layer
# Checks health of service layer services (API, Worker, and microservices)

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
    log_info "Health Check - Service Layer"
    log_info "=========================================="
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info ""
    
    # Core Services
    log_info "--- Core Services ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "api-service" "8000/health" "API Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "worker-service" "8080/healthz" "Worker Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Microservices
    log_info "--- Microservices ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "semantic-service" "8081/health" "Semantic Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "dq-service" "8083/health" "DQ Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "compliance-service" "8082/health" "Compliance Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "datacontract-service" "8080/health" "DataContract Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "search-service" "8085/health" "Search Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "observability-service" "8086/health" "Observability Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "webhook-service" "8087/health" "Webhook Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "prefect-integration-service" "8084/health" "Prefect Integration Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Dependencies
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
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "minio" "9000/minio/health/live" "MinIO"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Print summary
    print_summary "${TOTAL}" "${PASSED}" "${FAILED}"
}

# Run main function
main "$@"

