#!/bin/bash
# Health Check Script - All Services
# Checks health of all services in the Docker Compose stack

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
    log_info "Health Check - All Services"
    log_info "=========================================="
    log_info "Compose file: ${COMPOSE_FILE}"
    log_info ""
    
    # Infrastructure Services
    log_info "--- Infrastructure Services ---"
    
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
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "fuseki" "3030/\$/ping" "Fuseki"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Core Application Services
    log_info "--- Core Application Services ---"
    
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
    
    # Workflow Services
    log_info "--- Workflow Services ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "workflow-engine-service" "8088/healthz" "Workflow Engine Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "workflow-registry-service" "8089/health" "Workflow Registry Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Event Bus Services
    log_info "--- Event Bus Services ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "event-bus-health-service" "8090/healthz" "Event Bus Health Service"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "event-schema-registry-service" "8091/health" "Event Schema Registry Service"; then
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
    
    # Prefect Services
    log_info "--- Prefect Services ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "prefect-server" "4200/health" "Prefect Server"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    echo ""
    
    # Monitoring Services
    log_info "--- Monitoring Services ---"
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "prometheus" "9090/-/healthy" "Prometheus"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "grafana" "3000/api/health" "Grafana"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "jaeger" "16686/" "Jaeger"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    TOTAL=$((TOTAL + 1))
    if check_service_health "alertmanager" "9093/-/healthy" "Alertmanager"; then
        PASSED=$((PASSED + 1))
    else
        FAILED=$((FAILED + 1))
    fi
    
    # Print summary
    print_summary "${TOTAL}" "${PASSED}" "${FAILED}"
}

# Run main function
main "$@"

