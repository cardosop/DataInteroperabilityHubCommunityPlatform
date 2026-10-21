#!/bin/bash
#
# Health Check Automation Script
#
# This script performs health checks on all services after deployment.
#
# Usage:
#   ./scripts/deploy_health_check.sh [--service SERVICE] [--timeout TIMEOUT] [--retries RETRIES]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE=""
TIMEOUT=30
RETRIES=5
BASE_URL="${BASE_URL:-http://localhost}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        --retries)
            RETRIES="$2"
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

check_health() {
    local service_name=$1
    local health_url=$2
    
    log_info "Checking health: $service_name ($health_url)"
    
    local attempt=1
    while [ $attempt -le $RETRIES ]; do
        if curl -f -s --max-time $TIMEOUT "$health_url" > /dev/null 2>&1; then
            log_info "✓ $service_name is healthy"
            return 0
        else
            if [ $attempt -lt $RETRIES ]; then
                log_warn "⚠ $service_name health check failed (attempt $attempt/$RETRIES), retrying..."
                sleep 5
            else
                log_error "✗ $service_name health check failed after $RETRIES attempts"
                return 1
            fi
        fi
        ((attempt++))
    done
    
    return 1
}

main() {
    log_info "=========================================="
    log_info "Service Health Check"
    log_info "=========================================="
    log_info ""
    
    # Define services
    declare -A services=(
        ["api-service"]="$BASE_URL:8000/health"
        ["worker-service"]="$BASE_URL:8080/healthz"
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
    
    # Check services
    if [ -n "$SERVICE" ]; then
        if [[ -v services["$SERVICE"] ]]; then
            if ! check_health "$SERVICE" "${services[$SERVICE]}"; then
                ((errors++))
            fi
        else
            log_error "Unknown service: $SERVICE"
            exit 1
        fi
    else
        # Check all services
        for service_name in "${!services[@]}"; do
            if ! check_health "$service_name" "${services[$service_name]}"; then
                ((errors++))
            fi
            log_info ""
        done
    fi
    
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All health checks passed"
    else
        log_error "✗ $errors health check(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

