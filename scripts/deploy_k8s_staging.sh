#!/bin/bash
#
# Kubernetes Staging Deployment Script
#
# This script deploys all Kubernetes manifests to staging environment.
#
# Usage:
#   ./scripts/deploy_k8s_staging.sh [--dry-run] [--service SERVICE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
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

deploy_service() {
    local service_path=$1
    local service_name=$2
    local overlay="staging"
    
    log_info "Deploying $service_name to staging..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would deploy: $service_path/overlays/$overlay"
        $KUSTOMIZE_CMD build "$service_path/overlays/$overlay" | $KUBECTL_CMD apply --dry-run=client -f -
        return 0
    fi
    
    # Build and apply
    if $KUSTOMIZE_CMD build "$service_path/overlays/$overlay" | $KUBECTL_CMD apply -f -; then
        log_info "✓ $service_name deployed successfully"
        
        # Wait for deployment to be ready
        if $KUBECTL_CMD wait --for=condition=available --timeout=300s deployment/$service_name -n "$(get_namespace $service_name)" 2>/dev/null; then
            log_info "✓ $service_name is ready"
        else
            log_warn "⚠ $service_name deployment may not be ready yet"
        fi
        
        return 0
    else
        log_error "✗ $service_name deployment failed"
        return 1
    fi
}

get_namespace() {
    local service_name=$1
    case $service_name in
        prefect-server|prefect-worker)
            echo "prefect"
            ;;
        *)
            echo "default"
            ;;
    esac
}

main() {
    log_info "=========================================="
    log_info "Kubernetes Staging Deployment"
    log_info "=========================================="
    log_info ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info ""
    fi
    
    # Check prerequisites
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl not found. Please install kubectl."
        exit 1
    fi
    
    if ! command -v kustomize &> /dev/null; then
        KUSTOMIZE_CMD="kubectl kustomize"
    fi
    
    # Check cluster connection
    if [ "$DRY_RUN" = false ]; then
        if ! $KUBECTL_CMD cluster-info &> /dev/null; then
            log_error "Cannot connect to Kubernetes cluster"
            exit 1
        fi
    fi
    
    local errors=0
    
    # Deploy services
    if [ -n "$SERVICE" ]; then
        case $SERVICE in
            prefect-server)
                deploy_service "k8s/prefect-server" "prefect-server" || ((errors++))
                ;;
            prefect-workers)
                deploy_service "k8s/prefect-workers" "prefect-worker" || ((errors++))
                ;;
            prefect-integration)
                deploy_service "k8s/prefect-integration" "prefect-integration-service" || ((errors++))
                ;;
            search-service)
                deploy_service "k8s/search-service" "search-service" || ((errors++))
                ;;
            observability-service)
                deploy_service "k8s/observability-service" "observability-service" || ((errors++))
                ;;
            webhook-service)
                deploy_service "k8s/webhook-service" "webhook-service" || ((errors++))
                ;;
            *)
                log_error "Unknown service: $SERVICE"
                exit 1
                ;;
        esac
    else
        # Deploy all services
        deploy_service "k8s/prefect-server" "prefect-server" || ((errors++))
        deploy_service "k8s/prefect-workers" "prefect-worker" || ((errors++))
        deploy_service "k8s/prefect-integration" "prefect-integration-service" || ((errors++))
        deploy_service "k8s/search-service" "search-service" || ((errors++))
        deploy_service "k8s/observability-service" "observability-service" || ((errors++))
        deploy_service "k8s/webhook-service" "webhook-service" || ((errors++))
    fi
    
    log_info ""
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All services deployed successfully"
    else
        log_error "✗ $errors deployment(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

