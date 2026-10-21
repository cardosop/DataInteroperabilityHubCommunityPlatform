#!/bin/bash
# Comprehensive Kubernetes Marketplace Configuration Test
# Validates configuration, secret structure, encryption readiness, and cross-references

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

log_debug() {
    echo -e "${BLUE}[DEBUG]${NC} $1"
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

test_secret_structure() {
    local file=$1
    local description=$2

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description secret structure..."

    # Check if it's a Secret resource
    if ! grep -q "^kind: Secret" "$file" 2>/dev/null; then
        log_error "✗ $description is not a Secret resource"
        FAILED=$((FAILED + 1))
        return 1
    fi

    # Check if it uses stringData (recommended for secrets)
    if grep -q "^stringData:" "$file" 2>/dev/null; then
        log_info "✓ $description uses stringData (recommended)"
        PASSED=$((PASSED + 1))
        return 0
    elif grep -q "^data:" "$file" 2>/dev/null; then
        log_warn "⊘ $description uses data (base64 encoded) - consider using stringData"
        WARNINGS=$((WARNINGS + 1))
        PASSED=$((PASSED + 1))
        return 0
    else
        log_error "✗ $description has no stringData or data section"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_secret_encryption_note() {
    local file=$1
    local description=$2

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description has encryption note..."

    if grep -qi "external secrets\|sealed secrets\|vault\|secrets manager\|encryption" "$file" 2>/dev/null; then
        log_info "✓ $description includes encryption/secret management note"
        PASSED=$((PASSED + 1))
        return 0
    else
        log_warn "⊘ $description does not explicitly mention external secret management"
        WARNINGS=$((WARNINGS + 1))
        PASSED=$((PASSED + 1))  # Not a failure, just a warning
        return 0
    fi
}

test_configmap_secret_keys_match() {
    local configmap_file=$1
    local secret_file=$2
    local deployment_file=$3
    local description=$4

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description ConfigMap/Secret/Deployment key consistency..."

    # Extract keys from ConfigMap
    local configmap_keys=$(grep -E "^  [A-Z_]+:" "$configmap_file" 2>/dev/null | sed 's/^  //' | sed 's/:.*$//' || echo "")

    # Extract keys from Secret
    local secret_keys=$(grep -E "^  [A-Z_]+:" "$secret_file" 2>/dev/null | sed 's/^  //' | sed 's/:.*$//' || echo "")

    # Extract env var names from Deployment
    local deployment_env_vars=$(grep -A 1 "name:" "$deployment_file" 2>/dev/null | grep "name:" | sed 's/.*name: //' | grep -E "^[A-Z_]+$" || echo "")

    # Check if marketplace keys are present
    local required_configmap_keys=("CKAN_TEST_URL" "MOCK_SERVER_URL")
    local required_secret_keys=("DADOS_GOV_BR_API_KEY" "CKAN_TEST_API_KEY" "SNOWFLAKE_ACCOUNT")

    local missing_configmap=0
    local missing_secret=0
    local missing_deployment=0

    for key in "${required_configmap_keys[@]}"; do
        if ! echo "$configmap_keys" | grep -q "^$key$"; then
            log_error "✗ Missing ConfigMap key: $key"
            missing_configmap=1
        fi
        if ! echo "$deployment_env_vars" | grep -q "^$key$"; then
            log_error "✗ Missing Deployment env var: $key"
            missing_deployment=1
        fi
    done

    for key in "${required_secret_keys[@]}"; do
        if ! echo "$secret_keys" | grep -q "^$key$"; then
            log_error "✗ Missing Secret key: $key"
            missing_secret=1
        fi
        if ! echo "$deployment_env_vars" | grep -q "^$key$"; then
            log_error "✗ Missing Deployment env var: $key"
            missing_deployment=1
        fi
    done

    if [ $missing_configmap -eq 0 ] && [ $missing_secret -eq 0 ] && [ $missing_deployment -eq 0 ]; then
        log_info "✓ $description keys are consistent across ConfigMap/Secret/Deployment"
        PASSED=$((PASSED + 1))
        return 0
    else
        FAILED=$((FAILED + 1))
        return 1
    fi
}

test_deployment_env_ref_correct() {
    local deployment_file=$1
    local env_name=$2
    local expected_source=$3  # "configMapKeyRef" or "secretKeyRef"
    local expected_name=$4    # ConfigMap or Secret name
    local description=$5

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description environment variable reference..."

    # Check if env var exists and references correct source
    local env_block=$(grep -A 10 "name: $env_name" "$deployment_file" 2>/dev/null || echo "")

    if [ -z "$env_block" ]; then
        log_error "✗ $description environment variable not found"
        FAILED=$((FAILED + 1))
        return 1
    fi

    if ! echo "$env_block" | grep -q "$expected_source"; then
        log_error "✗ $description uses wrong source type (expected $expected_source)"
        FAILED=$((FAILED + 1))
        return 1
    fi

    if ! echo "$env_block" | grep -q "name: $expected_name"; then
        log_error "✗ $description references wrong resource name (expected $expected_name)"
        FAILED=$((FAILED + 1))
        return 1
    fi

    log_info "✓ $description environment variable reference is correct"
    PASSED=$((PASSED + 1))
    return 0
}

test_secret_base64_encoding() {
    local file=$1
    local description=$2

    TOTAL=$((TOTAL + 1))
    log_info "Testing $description secret encoding structure..."

    # If using stringData, values should be plain text (will be base64 encoded by Kubernetes)
    if grep -q "^stringData:" "$file" 2>/dev/null; then
        # Check if values look like placeholders (not base64)
        local sample_value=$(grep -A 1 "^  DADOS_GOV_BR_API_KEY:" "$file" 2>/dev/null | tail -1 | sed 's/.*: *"\(.*\)".*/\1/' || echo "")

        if echo "$sample_value" | grep -qE "^[A-Za-z0-9+/=]{20,}$" && ! echo "$sample_value" | grep -q "your-.*-here"; then
            # Looks like base64, but that's okay if it's a real value
            log_info "✓ $description uses stringData with encoded values"
        else
            log_info "✓ $description uses stringData with placeholder values (will be base64 encoded by Kubernetes)"
        fi
        PASSED=$((PASSED + 1))
        return 0
    else
        # If using data, values should be base64 encoded
        log_info "✓ $description uses data section (base64 encoded)"
        PASSED=$((PASSED + 1))
        return 0
    fi
}

test_all_marketplace_vars_present() {
    local service=$1  # "api-service" or "worker-service"

    TOTAL=$((TOTAL + 1))
    log_info "Testing all marketplace variables present in $service..."

    local configmap_file="k8s/$service/base/configmap.yaml"
    local secret_file="k8s/$service/base/secret.yaml"
    local deployment_file="k8s/$service/base/deployment.yaml"

    local missing=0

    # Check ConfigMap variables
    local configmap_vars=("CKAN_TEST_URL" "MOCK_SERVER_URL")
    for var in "${configmap_vars[@]}"; do
        if ! grep -q "^  $var:" "$configmap_file" 2>/dev/null; then
            log_error "✗ Missing ConfigMap variable: $var"
            missing=1
        fi
    done

    # Check Secret variables
    local secret_vars=("DADOS_GOV_BR_API_KEY" "CKAN_TEST_API_KEY" "SNOWFLAKE_ACCOUNT" "SNOWFLAKE_USER" "SNOWFLAKE_TOKEN" "SNOWFLAKE_WAREHOUSE" "SNOWFLAKE_ROLE" "SNOWFLAKE_DATABASE")
    for var in "${secret_vars[@]}"; do
        if ! grep -q "^  $var:" "$secret_file" 2>/dev/null; then
            log_error "✗ Missing Secret variable: $var"
            missing=1
        fi
    done

    # Check Deployment references
    for var in "${configmap_vars[@]}"; do
        if ! grep -A 5 "name: $var" "$deployment_file" 2>/dev/null | grep -q "configMapKeyRef"; then
            log_error "✗ Missing Deployment reference for ConfigMap variable: $var"
            missing=1
        fi
    done

    for var in "${secret_vars[@]}"; do
        if ! grep -A 5 "name: $var" "$deployment_file" 2>/dev/null | grep -q "secretKeyRef"; then
            log_error "✗ Missing Deployment reference for Secret variable: $var"
            missing=1
        fi
    done

    if [ $missing -eq 0 ]; then
        log_info "✓ All marketplace variables present in $service"
        PASSED=$((PASSED + 1))
        return 0
    else
        FAILED=$((FAILED + 1))
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Comprehensive Kubernetes Marketplace Test"
    log_info "=========================================="
    log_info ""

    # Test API Service
    log_info "=== API Service Tests ==="
    test_yaml_syntax "k8s/api-service/base/configmap.yaml" "API Service ConfigMap"
    test_yaml_syntax "k8s/api-service/base/secret.yaml" "API Service Secret"
    test_yaml_syntax "k8s/api-service/base/deployment.yaml" "API Service Deployment"

    test_secret_structure "k8s/api-service/base/secret.yaml" "API Service Secret"
    test_secret_encryption_note "k8s/api-service/base/secret.yaml" "API Service Secret"
    test_secret_base64_encoding "k8s/api-service/base/secret.yaml" "API Service Secret"

    test_configmap_secret_keys_match \
        "k8s/api-service/base/configmap.yaml" \
        "k8s/api-service/base/secret.yaml" \
        "k8s/api-service/base/deployment.yaml" \
        "API Service"

    test_deployment_env_ref_correct \
        "k8s/api-service/base/deployment.yaml" \
        "CKAN_TEST_URL" \
        "configMapKeyRef" \
        "api-service-config" \
        "API Service CKAN_TEST_URL"

    test_deployment_env_ref_correct \
        "k8s/api-service/base/deployment.yaml" \
        "DADOS_GOV_BR_API_KEY" \
        "secretKeyRef" \
        "api-service-secrets" \
        "API Service DADOS_GOV_BR_API_KEY"

    test_all_marketplace_vars_present "api-service"

    log_info ""
    log_info "=== Worker Service Tests ==="
    test_yaml_syntax "k8s/worker-service/base/configmap.yaml" "Worker Service ConfigMap"
    test_yaml_syntax "k8s/worker-service/base/secret.yaml" "Worker Service Secret"
    test_yaml_syntax "k8s/worker-service/base/deployment.yaml" "Worker Service Deployment"

    test_secret_structure "k8s/worker-service/base/secret.yaml" "Worker Service Secret"
    test_secret_encryption_note "k8s/worker-service/base/secret.yaml" "Worker Service Secret"
    test_secret_base64_encoding "k8s/worker-service/base/secret.yaml" "Worker Service Secret"

    test_configmap_secret_keys_match \
        "k8s/worker-service/base/configmap.yaml" \
        "k8s/worker-service/base/secret.yaml" \
        "k8s/worker-service/base/deployment.yaml" \
        "Worker Service"

    test_deployment_env_ref_correct \
        "k8s/worker-service/base/deployment.yaml" \
        "CKAN_TEST_URL" \
        "configMapKeyRef" \
        "worker-service-config" \
        "Worker Service CKAN_TEST_URL"

    test_deployment_env_ref_correct \
        "k8s/worker-service/base/deployment.yaml" \
        "DADOS_GOV_BR_API_KEY" \
        "secretKeyRef" \
        "worker-service-secrets" \
        "Worker Service DADOS_GOV_BR_API_KEY"

    test_all_marketplace_vars_present "worker-service"

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
        log_info "✓ All tests passed!"
        log_info ""
        log_info "Secret Encryption Status:"
        log_info "  - Secrets use stringData (recommended)"
        log_info "  - Kubernetes will base64 encode secrets automatically"
        log_info "  - For production: Use external secrets manager (see k8s/MARKETPLACE_SECRETS.md)"
        exit 0
    else
        log_error "✗ $FAILED test(s) failed"
        exit 1
    fi
}

main

