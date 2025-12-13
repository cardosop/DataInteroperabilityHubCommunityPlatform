#!/bin/bash
#
# Kubernetes Deployment Testing Script
#
# This script validates and tests Kubernetes deployment.
#
# Usage:
#   ./scripts/test_k8s_deployment.sh [--dry-run] [--namespace NAMESPACE] [--service SERVICE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

DRY_RUN=false
NAMESPACE="default"
SERVICE=""
KUBECTL_CMD="kubectl"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        --service)
            SERVICE="$2"
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

validate_manifests() {
    local service_path=$1
    local service_name=$2
    
    log_info "Validating manifests: $service_name"
    
    if [ "$DRY_RUN" = true ]; then
        if kubectl kustomize "$service_path/base" | kubectl apply --dry-run=client -f - > /dev/null 2>&1; then
            log_info "✓ $service_name manifests are valid"
            return 0
        else
            log_error "✗ $service_name manifests validation failed"
            kubectl kustomize "$service_path/base" | kubectl apply --dry-run=client -f -
            return 1
        fi
    else
        if kubectl apply --dry-run=client -k "$service_path/base" > /dev/null 2>&1; then
            log_info "✓ $service_name manifests are valid"
            return 0
        else
            log_error "✗ $service_name manifests validation failed"
            kubectl apply --dry-run=client -k "$service_path/base"
            return 1
        fi
    fi
}

check_pod_status() {
    local service_name=$1
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would check pod status for $service_name"
        return 0
    fi
    
    log_info "Checking pod status: $service_name"
    
    local pods
    pods=$(kubectl get pods -n "$NAMESPACE" -l app="$service_name" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$pods" ]; then
        log_error "✗ No pods found for $service_name"
        return 1
    fi
    
    local all_ready=true
    for pod in $pods; do
        local status
        status=$(kubectl get pod "$pod" -n "$NAMESPACE" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
        if [ "$status" != "Running" ]; then
            log_error "✗ Pod $pod is not Running (status: $status)"
            all_ready=false
        else
            log_info "✓ Pod $pod is Running"
        fi
    done
    
    if [ "$all_ready" = true ]; then
        return 0
    else
        return 1
    fi
}

test_service_discovery() {
    local service_name=$1
    local target_service=$2
    local target_port=$3
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would test service discovery: $service_name → $target_service:$target_port"
        return 0
    fi
    
    log_info "Testing service discovery: $service_name → $target_service:$target_port"
    
    # Get a pod from the service
    local pod
    pod=$(kubectl get pods -n "$NAMESPACE" -l app="$service_name" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
    
    if [ -z "$pod" ]; then
        log_error "✗ No pods found for $service_name"
        return 1
    fi
    
    # Test DNS resolution
    if kubectl exec -n "$NAMESPACE" "$pod" -- nslookup "$target_service" > /dev/null 2>&1; then
        log_info "✓ DNS resolution works for $target_service"
    else
        log_error "✗ DNS resolution failed for $target_service"
        return 1
    fi
    
    # Test connectivity
    if kubectl exec -n "$NAMESPACE" "$pod" -- sh -c "timeout 2 nc -z $target_service $target_port" > /dev/null 2>&1; then
        log_info "✓ $service_name can reach $target_service:$target_port"
        return 0
    else
        log_error "✗ $service_name cannot reach $target_service:$target_port"
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Kubernetes Deployment Testing"
    log_info "=========================================="
    log_info ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info ""
    fi
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check cluster connection
    if [ "$DRY_RUN" = false ]; then
        if ! kubectl cluster-info &> /dev/null; then
            log_error "Cannot connect to Kubernetes cluster"
            exit 1
        fi
    fi
    
    local errors=0
    
    # Define services to test
    declare -A services=(
        ["api-service"]="k8s/api-service"
        ["worker-service"]="k8s/worker-service"
        ["prefect-integration-service"]="k8s/prefect-integration"
        ["search-service"]="k8s/search-service"
        ["observability-service"]="k8s/observability-service"
        ["webhook-service"]="k8s/webhook-service"
    )
    
    # Validate and test services
    if [ -n "$SERVICE" ]; then
        if [[ -v services["$SERVICE"] ]]; then
            if ! validate_manifests "${services[$SERVICE]}" "$SERVICE"; then
                ((errors++))
            fi
            if [ "$DRY_RUN" = false ]; then
                if ! check_pod_status "$SERVICE"; then
                    ((errors++))
                fi
            fi
        else
            log_error "Unknown service: $SERVICE"
            exit 1
        fi
    else
        # Test all services
        for service_name in "${!services[@]}"; do
            if ! validate_manifests "${services[$service_name]}" "$service_name"; then
                ((errors++))
            fi
            if [ "$DRY_RUN" = false ]; then
                if ! check_pod_status "$service_name"; then
                    ((errors++))
                fi
            fi
            log_info ""
        done
    fi
    
    # Test service discovery (if not dry-run)
    if [ "$DRY_RUN" = false ] && [ $errors -eq 0 ]; then
        log_info "Testing service discovery..."
        if test_service_discovery "api-service" "postgres" "5432"; then
            log_info "✓ Service discovery works"
        else
            ((errors++))
        fi
    fi
    
    log_info ""
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All tests passed"
    else
        log_error "✗ $errors test(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

main

