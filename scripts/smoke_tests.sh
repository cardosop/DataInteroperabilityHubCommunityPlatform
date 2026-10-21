#!/bin/bash
#
# Smoke Test Automation Script
#
# This script runs smoke tests on all services after deployment.
#
# Usage:
#   ./scripts/smoke_tests.sh [--service SERVICE] [--base-url BASE_URL]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE=""
BASE_URL="${BASE_URL:-http://localhost}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --base-url)
            BASE_URL="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

test_endpoint() {
    local service_name=$1
    local endpoint=$2
    local expected_status=${3:-200}
    
    log_info "Testing: $service_name ($endpoint)"
    
    local status_code
    status_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$endpoint" || echo "000")
    
    if [ "$status_code" = "$expected_status" ]; then
        log_info "✓ $service_name endpoint responded with $status_code"
        return 0
    else
        log_error "✗ $service_name endpoint returned $status_code (expected $expected_status)"
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Smoke Tests"
    log_info "=========================================="
    log_info ""
    
    # Define service endpoints
    declare -A endpoints=(
        ["api-service"]="$BASE_URL:8000/api/v1/health"
        ["datacontract-service"]="$BASE_URL:8080/health"
        ["compliance-service"]="$BASE_URL:8082/health"
        ["dq-service"]="$BASE_URL:8083/health"
        ["semantic-service"]="$BASE_URL:8081/health"
        ["prefect-integration-service"]="$BASE_URL:8084/health"
        ["search-service"]="$BASE_URL:8085/health"
        ["observability-service"]="$BASE_URL:8086/health"
        ["webhook-service"]="$BASE_URL:8087/health"
    )
    
    local errors=0
    
    # Test services
    if [ -n "$SERVICE" ]; then
        if [[ -v endpoints["$SERVICE"] ]]; then
            if ! test_endpoint "$SERVICE" "${endpoints[$SERVICE]}"; then
                ((errors++))
            fi
        else
            log_error "Unknown service: $SERVICE"
            exit 1
        fi
    else
        # Test all services
        for service_name in "${!endpoints[@]}"; do
            if ! test_endpoint "$service_name" "${endpoints[$service_name]}"; then
                ((errors++))
            fi
            log_info ""
        done
    fi
    
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All smoke tests passed"
    else
        log_error "✗ $errors smoke test(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

