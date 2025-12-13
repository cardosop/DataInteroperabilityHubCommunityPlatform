#!/bin/bash
# Deploy Microservices Infrastructure
#
# This script deploys all microservices infrastructure components:
# - Namespaces
# - API Gateway (Traefik)
# - Monitoring (Prometheus, Grafana, Jaeger)
# - Logging (Loki, Promtail)
#
# Usage:
#   ./scripts/k8s/deploy-infrastructure.sh [--dry-run]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

DRY_RUN="${1:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    
    if ! command -v kubectl &> /dev/null; then
        log_error "kubectl is not installed"
        exit 1
    fi
    
    if ! kubectl cluster-info &> /dev/null; then
        log_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

deploy_namespaces() {
    log_info "Deploying namespaces..."
    
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -f "${PROJECT_ROOT}/k8s/namespaces/microservices-namespaces.yaml" --dry-run=client
    else
        kubectl apply -f "${PROJECT_ROOT}/k8s/namespaces/microservices-namespaces.yaml"
        log_info "Namespaces deployed"
    fi
}

deploy_api_gateway() {
    log_info "Deploying API Gateway (Traefik)..."
    
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/api-gateway/traefik/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/api-gateway/traefik/"
        log_info "API Gateway deployed"
    fi
}

deploy_monitoring() {
    log_info "Deploying monitoring stack..."
    
    # Prometheus
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/prometheus/base/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/prometheus/base/"
    fi
    
    # Grafana
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/grafana/base/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/grafana/base/"
    fi
    
    # Jaeger
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/jaeger/base/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/jaeger/base/"
    fi
    
    # Alertmanager
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/alertmanager/base/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/alertmanager/base/"
    fi
    
    log_info "Monitoring stack deployed"
}

deploy_logging() {
    log_info "Deploying logging stack..."
    
    # Loki
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/logging/loki/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/logging/loki/"
    fi
    
    # Promtail
    if [ "$DRY_RUN" = "--dry-run" ]; then
        kubectl apply -k "${PROJECT_ROOT}/k8s/logging/promtail/" --dry-run=client
    else
        kubectl apply -k "${PROJECT_ROOT}/k8s/logging/promtail/"
    fi
    
    log_info "Logging stack deployed"
}

verify_deployment() {
    if [ "$DRY_RUN" = "--dry-run" ]; then
        log_info "Dry-run mode - skipping verification"
        return
    fi
    
    log_info "Verifying deployment..."
    
    # Check namespaces
    log_info "Checking namespaces..."
    kubectl get namespaces | grep -E "(contract-service|asset-service|api-gateway|monitoring|logging)" || log_warn "Some namespaces not found"
    
    # Check API Gateway
    log_info "Checking API Gateway..."
    kubectl get pods -n api-gateway || log_warn "API Gateway pods not found"
    
    # Check Monitoring
    log_info "Checking monitoring stack..."
    kubectl get pods -n monitoring || log_warn "Monitoring pods not found"
    
    # Check Logging
    log_info "Checking logging stack..."
    kubectl get pods -n logging || log_warn "Logging pods not found"
    
    log_info "Verification complete"
}

main() {
    log_info "Starting infrastructure deployment..."
    
    check_prerequisites
    deploy_namespaces
    deploy_api_gateway
    deploy_monitoring
    deploy_logging
    verify_deployment
    
    log_info "Infrastructure deployment complete!"
    
    if [ "$DRY_RUN" != "--dry-run" ]; then
        log_info "Next steps:"
        log_info "1. Deploy microservices: kubectl apply -k k8s/<service-name>/base/"
        log_info "2. Verify services: kubectl get pods --all-namespaces"
        log_info "3. Access Grafana: kubectl port-forward -n monitoring svc/grafana 3000:3000"
        log_info "4. Access Jaeger: kubectl port-forward -n monitoring svc/jaeger 16686:16686"
    fi
}

main "$@"

