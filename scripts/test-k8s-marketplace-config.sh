#!/bin/bash
# Test Kubernetes Marketplace Configuration
# Validates that all marketplace connector configurations are properly set up in Kubernetes manifests

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

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

test_yaml_syntax() {
    local file=$1
    local description=$2

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description YAML syntax..."

    if python3 -c "import yaml; yaml.safe_load(open('$file'))" 2>/dev/null; then
        log_info "✓ $description YAML syntax is valid"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description YAML syntax is invalid"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_configmap_contains() {
    local file=$1
    local key=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in ConfigMap..."

    if grep -q "^  $key:" "$file" 2>/dev/null; then
        log_info "✓ $description found in ConfigMap"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description not found in ConfigMap"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_secret_contains() {
    local file=$1
    local key=$2
    local description=$3

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in Secret..."

    if grep -q "^  $key:" "$file" 2>/dev/null; then
        log_info "✓ $description found in Secret"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description not found in Secret"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_deployment_env_ref() {
    local file=$1
    local env_name=$2
    local source_type=$3  # "configMapKeyRef" or "secretKeyRef"
    local description=$4

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description in Deployment..."

    if grep -A 3 "name: $env_name" "$file" | grep -q "$source_type"; then
        log_info "✓ $description environment variable reference found in Deployment"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description environment variable reference not found in Deployment"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_secret_encryption_note() {
    local file=$1
    local description=$2

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description has encryption note..."

    if grep -qi "external secrets\|sealed secrets\|vault\|secrets manager" "$file" 2>/dev/null; then
        log_info "✓ $description includes encryption/secret management note"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_warn "⊘ $description does not explicitly mention external secret management (recommended but not required)"
        PASSED=$((PASSED + 1))  # Not a failure, just a warning
        return 0
    fi
}

main() {
    log_info "=========================================="
    log_info "Kubernetes Marketplace Configuration Test"
    log_info "=========================================="
    log_info ""

    # Test API Service ConfigMap
    log_info "--- API Service ConfigMap Tests ---"
    test_yaml_syntax "k8s/api-service/base/configmap.yaml" "API Service ConfigMap"
    test_configmap_contains "k8s/api-service/base/configmap.yaml" "CKAN_TEST_URL" "CKAN_TEST_URL"
    test_configmap_contains "k8s/api-service/base/configmap.yaml" "MOCK_SERVER_URL" "MOCK_SERVER_URL"

    # Test API Service Secret
    log_info ""
    log_info "--- API Service Secret Tests ---"
    test_yaml_syntax "k8s/api-service/base/secret.yaml" "API Service Secret"
    test_secret_contains "k8s/api-service/base/secret.yaml" "DADOS_GOV_BR_API_KEY" "DADOS_GOV_BR_API_KEY"
    test_secret_contains "k8s/api-service/base/secret.yaml" "CKAN_TEST_API_KEY" "CKAN_TEST_API_KEY"
    test_secret_contains "k8s/api-service/base/secret.yaml" "SNOWFLAKE_ACCOUNT" "SNOWFLAKE_ACCOUNT"
    test_secret_encryption_note "k8s/api-service/base/secret.yaml" "API Service Secret"

    # Test API Service Deployment
    log_info ""
    log_info "--- API Service Deployment Tests ---"
    test_yaml_syntax "k8s/api-service/base/deployment.yaml" "API Service Deployment"
    test_deployment_env_ref "k8s/api-service/base/deployment.yaml" "CKAN_TEST_URL" "configMapKeyRef" "CKAN_TEST_URL"
    test_deployment_env_ref "k8s/api-service/base/deployment.yaml" "MOCK_SERVER_URL" "configMapKeyRef" "MOCK_SERVER_URL"
    test_deployment_env_ref "k8s/api-service/base/deployment.yaml" "DADOS_GOV_BR_API_KEY" "secretKeyRef" "DADOS_GOV_BR_API_KEY"
    test_deployment_env_ref "k8s/api-service/base/deployment.yaml" "CKAN_TEST_API_KEY" "secretKeyRef" "CKAN_TEST_API_KEY"
    test_deployment_env_ref "k8s/api-service/base/deployment.yaml" "SNOWFLAKE_ACCOUNT" "secretKeyRef" "SNOWFLAKE_ACCOUNT"

    # Test Worker Service ConfigMap
    log_info ""
    log_info "--- Worker Service ConfigMap Tests ---"
    test_yaml_syntax "k8s/worker-service/base/configmap.yaml" "Worker Service ConfigMap"
    test_configmap_contains "k8s/worker-service/base/configmap.yaml" "CKAN_TEST_URL" "CKAN_TEST_URL"
    test_configmap_contains "k8s/worker-service/base/configmap.yaml" "MOCK_SERVER_URL" "MOCK_SERVER_URL"

    # Test Worker Service Secret
    log_info ""
    log_info "--- Worker Service Secret Tests ---"
    test_yaml_syntax "k8s/worker-service/base/secret.yaml" "Worker Service Secret"
    test_secret_contains "k8s/worker-service/base/secret.yaml" "DADOS_GOV_BR_API_KEY" "DADOS_GOV_BR_API_KEY"
    test_secret_contains "k8s/worker-service/base/secret.yaml" "CKAN_TEST_API_KEY" "CKAN_TEST_API_KEY"
    test_secret_contains "k8s/worker-service/base/secret.yaml" "SNOWFLAKE_ACCOUNT" "SNOWFLAKE_ACCOUNT"
    test_secret_encryption_note "k8s/worker-service/base/secret.yaml" "Worker Service Secret"

    # Test Worker Service Deployment
    log_info ""
    log_info "--- Worker Service Deployment Tests ---"
    test_yaml_syntax "k8s/worker-service/base/deployment.yaml" "Worker Service Deployment"
    test_deployment_env_ref "k8s/worker-service/base/deployment.yaml" "CKAN_TEST_URL" "configMapKeyRef" "CKAN_TEST_URL"
    test_deployment_env_ref "k8s/worker-service/base/deployment.yaml" "MOCK_SERVER_URL" "configMapKeyRef" "MOCK_SERVER_URL"
    test_deployment_env_ref "k8s/worker-service/base/deployment.yaml" "DADOS_GOV_BR_API_KEY" "secretKeyRef" "DADOS_GOV_BR_API_KEY"
    test_deployment_env_ref "k8s/worker-service/base/deployment.yaml" "CKAN_TEST_API_KEY" "secretKeyRef" "CKAN_TEST_API_KEY"
    test_deployment_env_ref "k8s/worker-service/base/deployment.yaml" "SNOWFLAKE_ACCOUNT" "secretKeyRef" "SNOWFLAKE_ACCOUNT"

    log_info ""
    log_info "=========================================="
    log_info "Test Summary"
    log_info "=========================================="
    log_info "Total Tests: $TOTAL"
    log_info "Passed: $PASSED"
    log_info "Failed: $FAILED"
    log_info "=========================================="

    if [ $FAILED -eq 0 ]; then
        log_info "✓ All tests passed!"
        log_info ""
        log_info "Note: Kubernetes Secrets are base64 encoded by default."
        log_info "For production, use external secrets manager (HashiCorp Vault, AWS Secrets Manager, etc.)"
        log_info "or Sealed Secrets / External Secrets Operator for encryption at rest."
        exit 0
    else
        log_error "✗ $FAILED test(s) failed"
        exit 1
    fi
}

main

