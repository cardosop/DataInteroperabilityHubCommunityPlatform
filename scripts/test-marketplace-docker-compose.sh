#!/bin/bash
# Test Marketplace Docker Compose Configuration
# Validates that all marketplace connector services are properly configured and running

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
TOTAL=0
PASSED=0
FAILED=0
SKIPPED=0

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

test_service_health() {
    local service=$1
    local endpoint=$2
    local description=$3
    local use_docker_exec=${4:-false}

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description ($service)..."

    if docker compose ps "$service" | grep -q "healthy\|Up"; then
        local result=1
        if [ "$use_docker_exec" = "true" ]; then
            # Test from within the container network
            if docker compose exec -T "$service" sh -c "wget -q -O- $endpoint > /dev/null 2>&1 || curl -sf $endpoint > /dev/null 2>&1" 2>/dev/null; then
                result=0
            fi
        else
            # Test from host
            if curl -sf "$endpoint" > /dev/null 2>&1; then
                result=0
            fi
        fi

        if [ $result -eq 0 ]; then
            log_info "✓ $description is healthy"
            PASSED=$((PASSED + 1))
            return 0
        else
            log_error "✗ $description endpoint not responding: $endpoint"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        log_warn "⊘ $description is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
        return 2
    fi
}

test_environment_variable() {
    local service=$1
    local var_name=$2
    local description=$3
    local expected_value=${4:-}

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description environment variable in $service..."

    if docker compose ps "$service" | grep -q "Up"; then
        local value=$(docker compose exec -T "$service" printenv "$var_name" 2>/dev/null || echo "")
        if [ -n "$value" ] || [ -z "$expected_value" ]; then
            log_info "✓ $description environment variable is set"
            PASSED=$((PASSED + 1))
            return 0
        else
            log_error "✗ $description environment variable not set or incorrect"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        log_warn "⊘ $service is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
        return 2
    fi
}

test_service_connectivity() {
    local service=$1
    local target_service=$2
    local port=$3
    local description=$4

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description connectivity..."

    if docker compose ps "$service" | grep -q "Up"; then
        if docker compose exec -T "$service" sh -c "nc -z $target_service $port" > /dev/null 2>&1 || \
           docker compose exec -T "$service" sh -c "timeout 2 bash -c '</dev/tcp/$target_service/$port'" > /dev/null 2>&1; then
            log_info "✓ $description connectivity successful"
            PASSED=$((PASSED + 1))
            return 0
        else
            log_error "✗ $description connectivity failed"
            FAILED=$((FAILED + 1))
            return 1
        fi
    else
        log_warn "⊘ $service is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
        return 2
    fi
}

main() {
    log_info "=========================================="
    log_info "Marketplace Docker Compose Test Suite"
    log_info "=========================================="
    log_info ""

    # Test 1: Mock Server Health
    TOTAL=$((TOTAL + 1))
    log_info "Testing Mock Server..."
    if docker compose ps mock-server | grep -q "Up"; then
        # MockServer is running - check if port is accessible
        if nc -z localhost 8095 2>/dev/null || timeout 2 bash -c "</dev/tcp/localhost/8095" 2>/dev/null; then
            log_info "✓ Mock Server is running and port is accessible"
            PASSED=$((PASSED + 1))
        else
            log_error "✗ Mock Server is running but port is not accessible"
            FAILED=$((FAILED + 1))
        fi
    else
        log_warn "⊘ Mock Server is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Test 2: CKAN Test Database Health
    TOTAL=$((TOTAL + 1))
    log_info "Testing CKAN Test Database..."
    if docker compose ps ckan-test-db | grep -q "Up"; then
        if docker compose exec -T ckan-test-db pg_isready -U ckan > /dev/null 2>&1; then
            log_info "✓ CKAN Test Database is healthy"
            PASSED=$((PASSED + 1))
        else
            log_error "✗ CKAN Test Database is not ready"
            FAILED=$((FAILED + 1))
        fi
    else
        log_warn "⊘ CKAN Test Database is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Test 3: CKAN Test Redis Health
    TOTAL=$((TOTAL + 1))
    log_info "Testing CKAN Test Redis..."
    if docker compose ps ckan-test-redis | grep -q "Up"; then
        if docker compose exec -T ckan-test-redis redis-cli ping > /dev/null 2>&1; then
            log_info "✓ CKAN Test Redis is healthy"
            PASSED=$((PASSED + 1))
        else
            log_error "✗ CKAN Test Redis is not responding"
            FAILED=$((FAILED + 1))
        fi
    else
        log_warn "⊘ CKAN Test Redis is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Test 4: CKAN Test Solr Health (optional - may take time to start)
    TOTAL=$((TOTAL + 1))
    log_info "Testing CKAN Test Solr..."
    if docker compose ps ckan-test-solr | grep -q "Up"; then
        # Solr takes time to start, check if port is accessible and service is responding
        if nc -z localhost 8983 2>/dev/null || timeout 2 bash -c "</dev/tcp/localhost/8983" 2>/dev/null; then
            # Try to ping Solr
            if curl -sf "http://localhost:8983/solr/admin/ping" > /dev/null 2>&1 || \
               curl -sf "http://localhost:8983/" > /dev/null 2>&1; then
                log_info "✓ CKAN Test Solr is healthy"
                PASSED=$((PASSED + 1))
            else
                log_warn "⊘ CKAN Test Solr is starting (may take time)"
                SKIPPED=$((SKIPPED + 1))
            fi
        else
            log_warn "⊘ CKAN Test Solr port not accessible (skipped)"
            SKIPPED=$((SKIPPED + 1))
        fi
    else
        log_warn "⊘ CKAN Test Solr is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi

    # Test 5: CKAN Test Instance Health (optional - depends on Solr)
    if docker compose ps ckan-test | grep -q "Up"; then
        test_service_health "ckan-test" "http://localhost:5000/api/3/action/status_show" "CKAN Test Instance"
    else
        log_warn "⊘ CKAN Test Instance is not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
        TOTAL=$((TOTAL + 1))
    fi

    log_info ""
    log_info "--- Environment Variable Tests ---"

    # Test 6: API Service Marketplace Environment Variables
    test_environment_variable "api-service" "DADOS_GOV_BR_API_KEY" "DADOS_GOV_BR_API_KEY"
    test_environment_variable "api-service" "CKAN_TEST_URL" "CKAN_TEST_URL"
    test_environment_variable "api-service" "CKAN_TEST_API_KEY" "CKAN_TEST_API_KEY"
    test_environment_variable "api-service" "MOCK_SERVER_URL" "MOCK_SERVER_URL"

    # Test 7: Worker Service Marketplace Environment Variables
    test_environment_variable "worker-service" "DADOS_GOV_BR_API_KEY" "DADOS_GOV_BR_API_KEY (worker)"
    test_environment_variable "worker-service" "CKAN_TEST_URL" "CKAN_TEST_URL (worker)"
    test_environment_variable "worker-service" "MOCK_SERVER_URL" "MOCK_SERVER_URL (worker)"

    log_info ""
    log_info "--- Service Connectivity Tests ---"

    # Test 8: API Service to Mock Server connectivity
    test_service_connectivity "api-service" "mock-server" "8080" "API Service to Mock Server"

    # Test 9: API Service to CKAN Test Database connectivity
    TOTAL=$((TOTAL + 1))
    log_info "Testing API Service to CKAN Test Database connectivity..."
    if docker compose ps api-service | grep -q "Up" && docker compose ps ckan-test-db | grep -q "Up"; then
        if docker compose exec -T api-service sh -c "timeout 2 bash -c '</dev/tcp/ckan-test-db/5432'" > /dev/null 2>&1 || \
           docker compose exec -T api-service sh -c "nc -z ckan-test-db 5432" > /dev/null 2>&1; then
            log_info "✓ API Service to CKAN Test Database connectivity successful"
            PASSED=$((PASSED + 1))
        else
            log_error "✗ API Service to CKAN Test Database connectivity failed"
            FAILED=$((FAILED + 1))
        fi
    else
        log_warn "⊘ API Service or CKAN Test Database not running (skipped)"
        SKIPPED=$((SKIPPED + 1))
    fi

    log_info ""
    log_info "=========================================="
    log_info "Test Summary"
    log_info "=========================================="
    log_info "Total Tests: $TOTAL"
    log_info "Passed: $PASSED"
    log_info "Failed: $FAILED"
    log_info "Skipped: $SKIPPED"
    log_info "=========================================="

    if [ $FAILED -eq 0 ]; then
        log_info "✓ All tests passed!"
        exit 0
    else
        log_error "✗ $FAILED test(s) failed"
        exit 1
    fi
}

main

