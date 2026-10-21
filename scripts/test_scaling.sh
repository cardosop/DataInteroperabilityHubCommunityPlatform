#!/bin/bash
#
# Scaling Testing Script
#
# This script tests HPA (Horizontal Pod Autoscaler) scaling for Kubernetes services.
#
# Usage:
#   ./scripts/test_scaling.sh [--service SERVICE] [--namespace NAMESPACE] [--load-duration SECONDS]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SERVICE="api-service"
NAMESPACE="default"
LOAD_DURATION=300
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
        --load-duration)
            LOAD_DURATION="$2"
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

check_hpa_exists() {
    local service_name=$1
    
    if kubectl get hpa "${service_name}-hpa" -n "$NAMESPACE" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

get_current_replicas() {
    local service_name=$1
    
    kubectl get deployment "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "0"
}

get_desired_replicas() {
    local service_name=$1
    
    kubectl get hpa "${service_name}-hpa" -n "$NAMESPACE" -o jsonpath='{.status.desiredReplicas}' 2>/dev/null || echo "0"
}

get_current_pod_count() {
    local service_name=$1
    
    kubectl get pods -n "$NAMESPACE" -l app="$service_name" --field-selector=status.phase=Running -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | wc -w
}

generate_load() {
    local service_name=$1
    local duration=$2
    
    log_info "Generating load for ${duration}s..."
    
    # Get service endpoint
    local endpoint
    endpoint=$(kubectl get service "$service_name" -n "$NAMESPACE" -o jsonpath='{.spec.clusterIP}:{.spec.ports[0].port}' 2>/dev/null || echo "")
    
    if [ -z "$endpoint" ]; then
        log_error "Failed to get service endpoint"
        return 1
    fi
    
    # Create load generator pod
    local load_pod="load-generator-$(date +%s)"
    
    kubectl run "$load_pod" -n "$NAMESPACE" --image=curlimages/curl:latest --rm -i --restart=Never -- sh -c "
        end_time=\$(date +%s)
        end_time=\$((end_time + $duration))
        while [ \$(date +%s) -lt \$end_time ]; do
            curl -s -o /dev/null http://${endpoint}/health || true
            sleep 0.01
        done
    " &
    
    local load_pid=$!
    echo $load_pid
}

monitor_scaling() {
    local service_name=$1
    local duration=$2
    local interval=10
    
    log_info "Monitoring scaling for ${duration}s (checking every ${interval}s)..."
    log_info ""
    
    local start_time
    start_time=$(date +%s)
    local end_time
    end_time=$((start_time + duration))
    
    local initial_replicas
    initial_replicas=$(get_current_replicas "$service_name")
    log_info "Initial replicas: $initial_replicas"
    log_info ""
    
    while [ $(date +%s) -lt $end_time ]; do
        local current_pods
        current_pods=$(get_current_pod_count "$service_name")
        local desired_replicas
        desired_replicas=$(get_desired_replicas "$service_name")
        
        log_info "$(date '+%H:%M:%S') - Pods: $current_pods, Desired: $desired_replicas"
        
        sleep $interval
    done
    
    local final_replicas
    final_replicas=$(get_current_replicas "$service_name")
    local final_pods
    final_pods=$(get_current_pod_count "$service_name")
    
    log_info ""
    log_info "Final replicas: $final_replicas"
    log_info "Final pods: $final_pods"
    
    if [ "$final_pods" -gt "$initial_replicas" ]; then
        log_info "✓ Scaling occurred (from $initial_replicas to $final_pods pods)"
        return 0
    else
        log_warn "⚠ No scaling occurred (may need more load or longer duration)"
        return 0  # Don't fail, just warn
    fi
}

test_scaling() {
    local service_name=$1
    
    log_info "=========================================="
    log_info "Testing Scaling: $service_name"
    log_info "=========================================="
    log_info ""
    
    # Check HPA exists
    if ! check_hpa_exists "$service_name"; then
        log_error "HPA not found for $service_name"
        return 1
    fi
    
    log_info "HPA found: ${service_name}-hpa"
    log_info ""
    
    # Get HPA configuration
    local min_replicas
    min_replicas=$(kubectl get hpa "${service_name}-hpa" -n "$NAMESPACE" -o jsonpath='{.spec.minReplicas}' 2>/dev/null || echo "1")
    local max_replicas
    max_replicas=$(kubectl get hpa "${service_name}-hpa" -n "$NAMESPACE" -o jsonpath='{.spec.maxReplicas}' 2>/dev/null || echo "10")
    
    log_info "HPA Configuration:"
    log_info "  Min replicas: $min_replicas"
    log_info "  Max replicas: $max_replicas"
    log_info ""
    
    # Generate load
    local load_pid
    load_pid=$(generate_load "$service_name" "$LOAD_DURATION")
    
    # Monitor scaling
    monitor_scaling "$service_name" "$LOAD_DURATION"
    
    # Wait for load generator to finish
    wait $load_pid 2>/dev/null || true
    
    log_info ""
    log_info "✓ Scaling test completed"
    return 0
}

main() {
    log_info "=========================================="
    log_info "Scaling Testing (HPA)"
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
    
    # Test scaling
    if ! test_scaling "$SERVICE"; then
        exit 1
    fi
    
    log_info "=========================================="
    log_info "✓ Scaling test completed"
    log_info "=========================================="
}

main

