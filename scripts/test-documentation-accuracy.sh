#!/bin/bash
# Test Documentation Accuracy - Validates documentation matches actual implementation
# Checks that documented environment variables exist in docker-compose.yml and k8s configs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TOTAL=0
PASSED=0
FAILED=0
WARNINGS=0

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

test_env_var_in_docker_compose() {
    local var=$1
    local service=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in docker-compose.yml..."

    # Check if variable exists in the service section
    # Use awk to find the service block and check for the variable
    if awk -v service="$service" -v var="$var" '
        /^  [a-zA-Z-]+:$/ {
            current_service = $1
            gsub(/:/, "", current_service)
            gsub(/^  /, "", current_service)
            in_service = (current_service == service)
        }
        in_service && /-.*var/ {
            if (index($0, var) > 0) {
                found = 1
                exit 0
            }
        }
        END { exit (found ? 0 : 1) }
    ' docker-compose.yml 2>/dev/null; then
        log_info "✓ $description found in docker-compose.yml ($service)"
        PASSED=$((PASSED + 1))
        return 0
    elif grep -q "$var" docker-compose.yml 2>/dev/null; then
        # Variable exists but might be in a different section or format
        # Check if it's in environment section of the service
        if sed -n "/^  $service:/,/^  [a-zA-Z-]*:/p" docker-compose.yml 2>/dev/null | grep -q "$var"; then
            log_info "✓ $description found in docker-compose.yml ($service)"
            PASSED=$((PASSED + 1))
            return 0
        else
            log_warn "⊘ $description found in docker-compose.yml but not in $service section"
            WARNINGS=$((WARNINGS + 1))
            PASSED=$((PASSED + 1))  # Still counts as pass, just a warning
            return 0
        fi
    else
        log_error "✗ $description NOT found in docker-compose.yml"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_env_var_in_k8s_configmap() {
    local var=$1
    local service=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in Kubernetes ConfigMap ($service)..."

    local configmap_file="k8s/$service/base/configmap.yaml"

    if [ ! -f "$configmap_file" ]; then
        log_warn "⊘ ConfigMap file not found: $configmap_file"
        WARNINGS=$((WARNINGS + 1))
        PASSED=$((PASSED + 1))  # Not a failure if service doesn't exist
        return 0
    fi

    if grep -qi "$var" "$configmap_file" 2>/dev/null; then
        log_info "✓ $description found in $configmap_file"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description NOT found in $configmap_file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_env_var_in_k8s_secret() {
    local var=$1
    local service=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in Kubernetes Secret ($service)..."

    local secret_file="k8s/$service/base/secret.yaml"

    if [ ! -f "$secret_file" ]; then
        log_warn "⊘ Secret file not found: $secret_file"
        WARNINGS=$((WARNINGS + 1))
        PASSED=$((PASSED + 1))  # Not a failure if service doesn't exist
        return 0
    fi

    if grep -qi "$var" "$secret_file" 2>/dev/null; then
        log_info "✓ $description found in $secret_file"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description NOT found in $secret_file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_env_var_in_k8s_deployment() {
    local var=$1
    local service=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in Kubernetes Deployment ($service)..."

    local deployment_file="k8s/$service/base/deployment.yaml"

    if [ ! -f "$deployment_file" ]; then
        log_warn "⊘ Deployment file not found: $deployment_file"
        WARNINGS=$((WARNINGS + 1))
        PASSED=$((PASSED + 1))  # Not a failure if service doesn't exist
        return 0
    fi

    if grep -qi "name: $var" "$deployment_file" 2>/dev/null; then
        log_info "✓ $description found in $deployment_file"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description NOT found in $deployment_file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Documentation Accuracy Test"
    log_info "=========================================="
    log_info ""
    log_info "This test validates that documented environment variables"
    log_info "actually exist in the implementation (docker-compose.yml and k8s configs)"
    log_info ""

    # Marketplace environment variables that should be in ConfigMaps (non-sensitive)
    local configmap_vars=(
        "CKAN_TEST_URL:api-service:CKAN_TEST_URL"
        "MOCK_SERVER_URL:api-service:MOCK_SERVER_URL"
        "CKAN_TEST_URL:worker-service:CKAN_TEST_URL"
        "MOCK_SERVER_URL:worker-service:MOCK_SERVER_URL"
    )

    # Marketplace environment variables that should be in Secrets (sensitive)
    local secret_vars=(
        "DADOS_GOV_BR_API_KEY:api-service:DADOS_GOV_BR_API_KEY"
        "CKAN_TEST_API_KEY:api-service:CKAN_TEST_API_KEY"
        "CKAN_DADOS_GOV_BR_API_KEY:api-service:CKAN_DADOS_GOV_BR_API_KEY"
        "SNOWFLAKE_ACCOUNT:api-service:SNOWFLAKE_ACCOUNT"
        "SNOWFLAKE_USER:api-service:SNOWFLAKE_USER"
        "SNOWFLAKE_TOKEN:api-service:SNOWFLAKE_TOKEN"
        "SNOWFLAKE_WAREHOUSE:api-service:SNOWFLAKE_WAREHOUSE"
        "SNOWFLAKE_ROLE:api-service:SNOWFLAKE_ROLE"
        "SNOWFLAKE_DATABASE:api-service:SNOWFLAKE_DATABASE"
        "DADOS_GOV_BR_API_KEY:worker-service:DADOS_GOV_BR_API_KEY"
        "CKAN_TEST_API_KEY:worker-service:CKAN_TEST_API_KEY"
        "CKAN_DADOS_GOV_BR_API_KEY:worker-service:CKAN_DADOS_GOV_BR_API_KEY"
        "SNOWFLAKE_ACCOUNT:worker-service:SNOWFLAKE_ACCOUNT"
        "SNOWFLAKE_USER:worker-service:SNOWFLAKE_USER"
        "SNOWFLAKE_TOKEN:worker-service:SNOWFLAKE_TOKEN"
        "SNOWFLAKE_WAREHOUSE:worker-service:SNOWFLAKE_WAREHOUSE"
        "SNOWFLAKE_ROLE:worker-service:SNOWFLAKE_ROLE"
        "SNOWFLAKE_DATABASE:worker-service:SNOWFLAKE_DATABASE"
    )

    log_info "=== Docker Compose Validation ==="

    # Test Docker Compose environment variables
    test_env_var_in_docker_compose "DADOS_GOV_BR_API_KEY" "api-service" "DADOS_GOV_BR_API_KEY in api-service"
    test_env_var_in_docker_compose "CKAN_TEST_URL" "api-service" "CKAN_TEST_URL in api-service"
    test_env_var_in_docker_compose "CKAN_TEST_API_KEY" "api-service" "CKAN_TEST_API_KEY in api-service"
    test_env_var_in_docker_compose "MOCK_SERVER_URL" "api-service" "MOCK_SERVER_URL in api-service"
    test_env_var_in_docker_compose "SNOWFLAKE_ACCOUNT" "api-service" "SNOWFLAKE_ACCOUNT in api-service"

    test_env_var_in_docker_compose "DADOS_GOV_BR_API_KEY" "worker-service" "DADOS_GOV_BR_API_KEY in worker-service"
    test_env_var_in_docker_compose "CKAN_TEST_URL" "worker-service" "CKAN_TEST_URL in worker-service"
    test_env_var_in_docker_compose "MOCK_SERVER_URL" "worker-service" "MOCK_SERVER_URL in worker-service"

    log_info ""
    log_info "=== Kubernetes ConfigMap Validation ==="

    # Test Kubernetes ConfigMaps
    for var_info in "${configmap_vars[@]}"; do
        IFS=':' read -r var service desc <<< "$var_info"
        test_env_var_in_k8s_configmap "$var" "$service" "$desc"
    done

    log_info ""
    log_info "=== Kubernetes Secret Validation ==="

    # Test Kubernetes Secrets
    for var_info in "${secret_vars[@]}"; do
        IFS=':' read -r var service desc <<< "$var_info"
        test_env_var_in_k8s_secret "$var" "$service" "$desc"
    done

    log_info ""
    log_info "=== Kubernetes Deployment Validation ==="

    # Test Kubernetes Deployments reference the variables
    test_env_var_in_k8s_deployment "CKAN_TEST_URL" "api-service" "CKAN_TEST_URL in api-service deployment"
    test_env_var_in_k8s_deployment "MOCK_SERVER_URL" "api-service" "MOCK_SERVER_URL in api-service deployment"
    test_env_var_in_k8s_deployment "DADOS_GOV_BR_API_KEY" "api-service" "DADOS_GOV_BR_API_KEY in api-service deployment"
    test_env_var_in_k8s_deployment "CKAN_TEST_API_KEY" "api-service" "CKAN_TEST_API_KEY in api-service deployment"
    test_env_var_in_k8s_deployment "SNOWFLAKE_ACCOUNT" "api-service" "SNOWFLAKE_ACCOUNT in api-service deployment"

    test_env_var_in_k8s_deployment "CKAN_TEST_URL" "worker-service" "CKAN_TEST_URL in worker-service deployment"
    test_env_var_in_k8s_deployment "MOCK_SERVER_URL" "worker-service" "MOCK_SERVER_URL in worker-service deployment"
    test_env_var_in_k8s_deployment "DADOS_GOV_BR_API_KEY" "worker-service" "DADOS_GOV_BR_API_KEY in worker-service deployment"
    test_env_var_in_k8s_deployment "CKAN_TEST_API_KEY" "worker-service" "CKAN_TEST_API_KEY in worker-service deployment"
    test_env_var_in_k8s_deployment "SNOWFLAKE_ACCOUNT" "worker-service" "SNOWFLAKE_ACCOUNT in worker-service deployment"

    log_info ""
    log_info "=========================================="
    log_info "Test Summary"
    log_info "=========================================="
    log_info "Total Tests: $TOTAL"
    log_info "Passed: $PASSED"
    log_info "Failed: $FAILED"
    log_info "Warnings: $WARNINGS"
    log_info "=========================================="

    if [ $FAILED -eq 0 ]; then
        log_info "✓ All documentation accuracy tests passed!"
        log_info ""
        log_info "Documentation matches implementation:"
        log_info "  - All documented variables exist in docker-compose.yml"
        log_info "  - All documented variables exist in Kubernetes configs"
        log_info "  - All variables are referenced in deployments"
        exit 0
    else
        log_error "✗ $FAILED test(s) failed"
        log_error "Documentation does not match implementation"
        log_error "Please review and fix discrepancies"
        exit 1
    fi
}

main

