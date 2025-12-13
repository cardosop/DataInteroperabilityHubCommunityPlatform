#!/bin/bash
#
# Kubernetes Manifests Testing Script
#
# This script validates and tests all Kubernetes manifests using kubectl and kustomize.
#
# Usage:
#   ./scripts/test_k8s_manifests.sh [--dry-run] [--namespace NAMESPACE] [--service SERVICE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
NAMESPACE=""
SERVICE=""
KUBECTL_CMD="kubectl"
KUSTOMIZE_CMD="kustomize"

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check kubectl
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    # Check kustomize
    if ! command -v kustomize &> /dev/null; then
        log_warn "kustomize not found. Installing via kubectl..."
        KUSTOMIZE_CMD="kubectl kustomize"
    fi
    
    log_info "Prerequisites check complete."
}

validate_manifest() {
    local manifest_path=$1
    local service_name=$2
    
    log_info "Validating $service_name manifests..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Validating: $manifest_path"
        if $KUSTOMIZE_CMD build "$manifest_path" > /dev/null 2>&1; then
            log_info "✓ $service_name manifests are valid"
            return 0
        else
            log_error "✗ $service_name manifests validation failed"
            return 1
        fi
    else
        # Build and validate with kubectl
        if $KUBECTL_CMD apply --dry-run=client -f <($KUSTOMIZE_CMD build "$manifest_path") > /dev/null 2>&1; then
            log_info "✓ $service_name manifests are valid"
            return 0
        else
            log_error "✗ $service_name manifests validation failed"
            $KUBECTL_CMD apply --dry-run=client -f <($KUSTOMIZE_CMD build "$manifest_path")
            return 1
        fi
    fi
}

test_service_health() {
    local service_name=$1
    local namespace=$2
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would check health for $service_name in namespace $namespace"
        return 0
    fi
    
    log_info "Checking health for $service_name..."
    
    # Wait for deployment to be ready
    if $KUBECTL_CMD wait --for=condition=available --timeout=300s deployment/$service_name -n "$namespace" 2>/dev/null; then
        log_info "✓ $service_name is healthy"
        return 0
    else
        log_error "✗ $service_name health check failed"
        return 1
    fi
}

test_all_services() {
    local environment=${1:-base}
    local errors=0
    
    log_info "Testing all services in $environment environment..."
    
    # Test Prefect Server
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "prefect-server" ]; then
        if ! validate_manifest "k8s/prefect-server/base" "prefect-server"; then
            ((errors++))
        fi
    fi
    
    # Test Prefect Workers
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "prefect-workers" ]; then
        if ! validate_manifest "k8s/prefect-workers/base" "prefect-workers"; then
            ((errors++))
        fi
    fi
    
    # Test Prefect Integration Service
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "prefect-integration" ]; then
        if ! validate_manifest "k8s/prefect-integration/base" "prefect-integration-service"; then
            ((errors++))
        fi
    fi
    
    # Test Search Service
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "search-service" ]; then
        if ! validate_manifest "k8s/search-service/base" "search-service"; then
            ((errors++))
        fi
    fi
    
    # Test Observability Service
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "observability-service" ]; then
        if ! validate_manifest "k8s/observability-service/base" "observability-service"; then
            ((errors++))
        fi
    fi
    
    # Test Webhook Service
    if [ -z "$SERVICE" ] || [ "$SERVICE" = "webhook-service" ]; then
        if ! validate_manifest "k8s/webhook-service/base" "webhook-service"; then
            ((errors++))
        fi
    fi
    
    return $errors
}

main() {
    log_info "=========================================="
    log_info "Kubernetes Manifests Testing"
    log_info "=========================================="
    log_info ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info ""
    fi
    
    # Pre-flight checks
    check_prerequisites
    
    # Test all services
    local errors=0
    
    if [ -n "$SERVICE" ]; then
        log_info "Testing specific service: $SERVICE"
        case $SERVICE in
            prefect-server)
                validate_manifest "k8s/prefect-server/base" "prefect-server" || ((errors++))
                ;;
            prefect-workers)
                validate_manifest "k8s/prefect-workers/base" "prefect-workers" || ((errors++))
                ;;
            prefect-integration)
                validate_manifest "k8s/prefect-integration/base" "prefect-integration-service" || ((errors++))
                ;;
            search-service)
                validate_manifest "k8s/search-service/base" "search-service" || ((errors++))
                ;;
            observability-service)
                validate_manifest "k8s/observability-service/base" "observability-service" || ((errors++))
                ;;
            webhook-service)
                validate_manifest "k8s/webhook-service/base" "webhook-service" || ((errors++))
                ;;
            *)
                log_error "Unknown service: $SERVICE"
                exit 1
                ;;
        esac
    else
        test_all_services || errors=$?
    fi
    
    log_info ""
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All manifest validations passed"
    else
        log_error "✗ $errors validation(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

