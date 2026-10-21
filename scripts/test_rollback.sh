#!/bin/bash
#
# Rollback Testing Script
#
# This script tests rollback procedures for Kubernetes deployments.
#
# Usage:
#   ./scripts/test_rollback.sh [--service SERVICE] [--namespace NAMESPACE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SERVICE=""
NAMESPACE="default"
KUBECTL_CMD="kubectl"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

get_current_revision() {
    local service_name=$1
    
    kubectl get deployment "$service_name" -n "$NAMESPACE" -o jsonpath='{.metadata.annotations.deployment\.kubernetes\.io/revision}' 2>/dev/null || echo "0"
}

rollback_deployment() {
    local service_name=$1
    
    log_info "Rolling back deployment: $service_name"
    
    if kubectl rollout undo deployment "$service_name" -n "$NAMESPACE"; then
        log_info "✓ Rollback initiated for $service_name"
        return 0
    else
        log_error "✗ Rollback failed for $service_name"
        return 1
    fi
}

wait_for_rollback() {
    local service_name=$1
    local timeout=${2:-300}
    
    log_info "Waiting for rollback to complete: $service_name (timeout: ${timeout}s)"
    
    if kubectl rollout status deployment "$service_name" -n "$NAMESPACE" --timeout="${timeout}s"; then
        log_info "✓ Rollback completed for $service_name"
        return 0
    else
        log_error "✗ Rollback timeout for $service_name"
        return 1
    fi
}

verify_service_health() {
    local service_name=$1
    
    log_info "Verifying service health: $service_name"
    
    # Get a pod
    local pod
    pod=$(kubectl get pods -n "$NAMESPACE" -l app="$service_name" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$pod" ]; then
        log_error "✗ No pods found for $service_name"
        return 1
    fi
    
    # Check pod is running
    local status
    status=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    
    if [ "$status" = "Running" ]; then
        log_info "✓ Pod $pod is Running"
        
        # Check readiness
        local ready
        ready=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")
        
        if [ "$ready" = "True" ]; then
            log_info "✓ Pod $pod is Ready"
            return 0
        else
            log_error "✗ Pod $pod is not Ready"
            return 1
        fi
    else
        log_error "✗ Pod $pod is not Running (status: $status)"
        return 1
    fi
}

test_rollback() {
    local service_name=$1
    
    log_info "=========================================="
    log_info "Testing Rollback: $service_name"
    log_info "=========================================="
    log_info ""
    
    # Get current revision
    local current_revision
    current_revision=$(get_current_revision "$service_name")
    log_info "Current revision: $current_revision"
    
    # Perform rollback
    if ! rollback_deployment "$service_name"; then
        return 1
    fi
    
    # Wait for rollback to complete
    if ! wait_for_rollback "$service_name"; then
        return 1
    fi
    
    # Verify service health
    if ! verify_service_health "$service_name"; then
        return 1
    fi
    
    # Get new revision
    local new_revision
    new_revision=$(get_current_revision "$service_name")
    log_info "New revision: $new_revision"
    
    if [ "$new_revision" != "$current_revision" ]; then
        log_info "✓ Revision changed (rollback successful)"
    else
        log_warn "⚠ Revision unchanged (may be first deployment)"
    fi
    
    log_info ""
    log_info "✓ Rollback test passed for $service_name"
    return 0
}

main() {
    log_info "=========================================="
    log_info "Rollback Testing"
    log_info "=========================================="
    log_info ""
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check cluster connection
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    local errors=0
    
    # Define services to test
    declare -a services=(
        "api-service"
        "worker-service"
        "semantic-service"
        "datacontract-service"
        "compliance-service"
        "dq-service"
    )
    
    # Test services
    if [ -n "$SERVICE" ]; then
        if [[ " ${services[@]} " =~ " ${SERVICE} " ]]; then
            if ! test_rollback "$SERVICE"; then
                ((errors++))
            fi
        else
            log_error "Unknown service: $SERVICE"
            exit 1
        fi
    else
        # Test all services
        for service in "${services[@]}"; do
            if ! test_rollback "$service"; then
                ((errors++))
            fi
            log_info ""
        done
    fi
    
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All rollback tests passed"
    else
        log_error "✗ $errors rollback test(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

main

