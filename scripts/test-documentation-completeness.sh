#!/bin/bash
# Test Documentation Completeness for Marketplace Environment Variables
# Validates that all marketplace-related environment variables are documented

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

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

test_doc_contains_variable() {
    local doc_file=$1
    local variable=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in $doc_file..."

    if grep -qi "$variable" "$doc_file" 2>/dev/null; then
        log_info "✓ $description found in $doc_file"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description NOT found in $doc_file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_doc_contains_section() {
    local doc_file=$1
    local section=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in $doc_file..."

    if grep -qi "$section" "$doc_file" 2>/dev/null; then
        log_info "✓ $description found in $doc_file"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description NOT found in $doc_file"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Documentation Completeness Test"
    log_info "=========================================="
    log_info ""

    # Required marketplace environment variables
    local marketplace_vars=(
        "DADOS_GOV_BR_API_KEY"
        "CKAN_DADOS_GOV_BR_API_KEY"
        "CKAN_TEST_URL"
        "CKAN_TEST_API_KEY"
        "SNOWFLAKE_ACCOUNT"
        "SNOWFLAKE_USER"
        "SNOWFLAKE_TOKEN"
        "SNOWFLAKE_WAREHOUSE"
        "SNOWFLAKE_ROLE"
        "SNOWFLAKE_DATABASE"
        "MOCK_SERVER_URL"
    )

    # Documentation files to test
    local docker_compose_doc="docs/DOCKER_COMPOSE_DEPLOYMENT.md"
    local k8s_doc="docs/KUBERNETES_DEPLOYMENT.md"

    log_info "=== Docker Compose Deployment Documentation ==="

    # Test Docker Compose documentation
    test_doc_contains_section "$docker_compose_doc" "Marketplace Connector Configuration" "Marketplace configuration section"
    test_doc_contains_section "$docker_compose_doc" "dados.gov.br" "dados.gov.br marketplace documentation"
    test_doc_contains_section "$docker_compose_doc" "CKAN Instances" "CKAN instances documentation"
    test_doc_contains_section "$docker_compose_doc" "Snowflake Data Marketplace" "Snowflake marketplace documentation"
    test_doc_contains_section "$docker_compose_doc" "Mock Server" "Mock server documentation"

    for var in "${marketplace_vars[@]}"; do
        test_doc_contains_variable "$docker_compose_doc" "$var" "$var environment variable"
    done

    log_info ""
    log_info "=== Kubernetes Deployment Documentation ==="

    # Test Kubernetes documentation
    test_doc_contains_section "$k8s_doc" "Marketplace Environment Variables" "Marketplace environment variables section"
    test_doc_contains_section "$k8s_doc" "Marketplace Connector Secrets" "Marketplace secrets section"
    test_doc_contains_section "$k8s_doc" "dados.gov.br" "dados.gov.br marketplace documentation"
    test_doc_contains_section "$k8s_doc" "CKAN Instances" "CKAN instances documentation"
    test_doc_contains_section "$k8s_doc" "Snowflake Data Marketplace" "Snowflake marketplace documentation"
    test_doc_contains_section "$k8s_doc" "Mock Server" "Mock server documentation"

    for var in "${marketplace_vars[@]}"; do
        test_doc_contains_variable "$k8s_doc" "$var" "$var environment variable"
    done

    # Test configuration requirements
    log_info ""
    log_info "=== Configuration Requirements Documentation ==="

    test_doc_contains_section "$docker_compose_doc" "Configuration Requirements" "Configuration requirements section"
    test_doc_contains_section "$k8s_doc" "Configuration Requirements" "Configuration requirements section"
    test_doc_contains_section "$docker_compose_doc" "JWT Bearer token" "JWT token documentation"
    test_doc_contains_section "$k8s_doc" "JWT Bearer token" "JWT token documentation"
    test_doc_contains_section "$docker_compose_doc" "Swagger API" "Swagger API documentation"
    test_doc_contains_section "$k8s_doc" "Swagger API" "Swagger API documentation"

    log_info ""
    log_info "=========================================="
    log_info "Test Summary"
    log_info "=========================================="
    log_info "Total Tests: $TOTAL"
    log_info "Passed: $PASSED"
    log_info "Failed: $FAILED"
    log_info "=========================================="

    if [ $FAILED -eq 0 ]; then
        log_info "✓ All documentation tests passed!"
        log_info ""
        log_info "Documentation is complete and includes:"
        log_info "  - All marketplace environment variables"
        log_info "  - Configuration requirements for each marketplace"
        log_info "  - Docker Compose deployment instructions"
        log_info "  - Kubernetes deployment instructions"
        exit 0
    else
        log_error "✗ $FAILED test(s) failed"
        log_error "Please review the documentation and add missing sections/variables"
        exit 1
    fi
}

main

