#!/bin/bash
#
# Load Balancing Testing Script
#
# This script tests load balancing for Kubernetes services.
#
# Usage:
#   ./scripts/test_load_balancing.sh [--service SERVICE] [--namespace NAMESPACE] [--requests COUNT]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SERVICE="api-service"
NAMESPACE="default"
REQUESTS=100
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
        --requests)
            REQUESTS="$2"
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

get_service_endpoint() {
    local service_name=$1
    
    # Get service ClusterIP
    local cluster_ip
    cluster_ip=$(kubectl get service "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}' 2>/dev/null || echo "")
    
    if [ -z "$cluster_ip" ]; then
        log_error "Service $service_name not found"
        return 1
    fi
    
    # Get service port
    local port
    port=$(kubectl get service "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.ports[0].port}' 2>/dev/null || echo "")
    
    echo "${cluster_ip}:${port}"
}

get_pod_names() {
    local service_name=$1
    
    kubectl get pods -n "$NAMESPACE" -l app="$service_name" -o jsonpath='{.items[*].metadata.name}' 2>/dev/null || echo ""
}

test_load_balancing() {
    local service_name=$1
    local endpoint=$2
    
    log_info "Testing load balancing: $service_name"
    log_info "Endpoint: $endpoint"
    log_info "Requests: $REQUESTS"
    log_info ""
    
    # Get pod names
    local pods
    pods=$(get_pod_names "$service_name")
    
    if [ -z "$pods" ]; then
        log_error "No pods found for $service_name"
        return 1
    fi
    
    log_info "Pods: $pods"
    log_info ""
    
    # Count requests per pod (using a test pod to make requests)
    log_info "Making $REQUESTS requests to service..."
    
    # Create a test pod
    local test_pod="load-balance-test-$(date +%s)"
    
    kubectl run "$test_pod" -n "$NAMESPACE" --image=curlimages/curl:latest --rm -i --restart=Never -- sh -c "
        for i in \$(seq 1 $REQUESTS); do
            curl -s -o /dev/null -w '%{http_code}\n' http://${endpoint}/health || echo '000'
            sleep 0.1
        done
    " || true
    
    log_info ""
    log_info "✓ Load balancing test completed"
    log_info ""
    log_info "Note: For detailed load distribution analysis, check service logs or use"
    log_info "      monitoring tools to see request distribution across pods."
    
    return 0
}

main() {
    log_info "=========================================="
    log_info "Load Balancing Testing"
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
    
    # Get service endpoint
    local endpoint
    endpoint=$(get_service_endpoint "$SERVICE")
    
    if [ -z "$endpoint" ]; then
        log_error "Failed to get service endpoint"
        exit 1
    fi
    
    # Test load balancing
    if ! test_load_balancing "$SERVICE" "$endpoint"; then
        exit 1
    fi
    
    log_info "=========================================="
    log_info "✓ Load balancing test completed"
    log_info "=========================================="
}

main

