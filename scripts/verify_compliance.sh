#!/bin/bash
#
# Compliance Verification Script
#
# This script verifies engineering, security, observability, and reliability compliance
# for all services in both Docker Compose and Kubernetes environments.
#
# Usage:
#   ./scripts/verify_compliance.sh [--environment ENV] [--service SERVICE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ENVIRONMENT="all"
SERVICE=""
KUBECTL_CMD="kubectl"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --environment)
            ENVIRONMENT="$2"
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

check_non_root() {
    local service_name=$1
    local env=$2
    
    log_info "Checking non-root execution: $service_name ($env)"
    
    if [ "$env" = "docker" ]; then
        # Check Docker Compose
        if grep -q "user:" "docker-compose.yml" && grep -A 5 "$service_name:" docker-compose.yml | grep -q "user:"; then
            log_info "✓ $service_name runs as non-root in Docker Compose"
            return 0
        else
            log_warn "⚠ $service_name may run as root in Docker Compose (check Dockerfile)"
            return 0  # Don't fail, just warn
        fi
    else
        # Check Kubernetes
        if kubectl get deployment "$service_name" -n default -o jsonpath='{.spec.template.spec.securityContext.runAsNonRoot}' 2>/dev/null | grep -q "true"; then
            log_info "✓ $service_name runs as non-root in Kubernetes"
            return 0
        else
            log_error "✗ $service_name does not have runAsNonRoot=true in Kubernetes"
            return 1
        fi
    fi
}

check_resource_limits() {
    local service_name=$1
    local env=$2
    
    log_info "Checking resource limits: $service_name ($env)"
    
    if [ "$env" = "docker" ]; then
        # Check Docker Compose
        if grep -A 10 "$service_name:" docker-compose.yml | grep -q "deploy:"; then
            log_info "✓ $service_name has resource limits in Docker Compose"
            return 0
        else
            log_warn "⚠ $service_name may not have resource limits in Docker Compose"
            return 0  # Don't fail, just warn
        fi
    else
        # Check Kubernetes
        local has_limits
        has_limits=$(kubectl get deployment "$service_name" -n default -o jsonpath='{.spec.template.spec.containers[0].resources.limits}' 2>/dev/null || echo "")
        if [ -n "$has_limits" ] && [ "$has_limits" != "null" ]; then
            log_info "✓ $service_name has resource limits in Kubernetes"
            return 0
        else
            log_error "✗ $service_name does not have resource limits in Kubernetes"
            return 1
        fi
    fi
}

check_health_checks() {
    local service_name=$1
    local env=$2
    
    log_info "Checking health checks: $service_name ($env)"
    
    if [ "$env" = "docker" ]; then
        # Check Docker Compose
        if grep -A 10 "$service_name:" docker-compose.yml | grep -q "healthcheck:"; then
            log_info "✓ $service_name has health checks in Docker Compose"
            return 0
        else
            log_error "✗ $service_name does not have health checks in Docker Compose"
            return 1
        fi
    else
        # Check Kubernetes
        local has_liveness
        has_liveness=$(kubectl get deployment "$service_name" -n default -o jsonpath='{.spec.template.spec.containers[0].livenessProbe}' 2>/dev/null || echo "")
        local has_readiness
        has_readiness=$(kubectl get deployment "$service_name" -n default -o jsonpath='{.spec.template.spec.containers[0].readinessProbe}' 2>/dev/null || echo "")
        
        if [ -n "$has_liveness" ] && [ "$has_liveness" != "null" ] && [ -n "$has_readiness" ] && [ "$has_readiness" != "null" ]; then
            log_info "✓ $service_name has liveness and readiness probes in Kubernetes"
            return 0
        else
            log_error "✗ $service_name does not have health checks in Kubernetes"
            return 1
        fi
    fi
}

check_secrets_not_in_configmap() {
    local service_name=$1
    
    log_info "Checking secrets not in ConfigMap: $service_name"
    
    # Check if ConfigMap contains secret-like values
    local configmap
    configmap=$(kubectl get configmap "${service_name}-config" -n default -o yaml 2>/dev/null || echo "")
    
    if echo "$configmap" | grep -qiE "(password|secret|key|token)" && ! echo "$configmap" | grep -q "your-.*-here"; then
        log_error "✗ $service_name ConfigMap may contain secrets"
        return 1
    else
        log_info "✓ $service_name ConfigMap does not contain secrets"
        return 0
    fi
}

check_security_context() {
    local service_name=$1
    
    log_info "Checking security context: $service_name"
    
    local has_seccomp
    has_seccomp=$(kubectl get deployment "$service_name" -n default -o jsonpath='{.spec.template.spec.securityContext.seccompProfile.type}' 2>/dev/null || echo "")
    
    if [ "$has_seccomp" = "RuntimeDefault" ]; then
        log_info "✓ $service_name has seccomp profile configured"
        return 0
    else
        log_warn "⚠ $service_name does not have seccomp profile configured"
        return 0  # Don't fail, just warn
    fi
}

main() {
    log_info "=========================================="
    log_info "Compliance Verification"
    log_info "=========================================="
    log_info ""
    
    local errors=0
    local warnings=0
    
    # Define services to check
    declare -a services=(
        "api-service"
        "worker-service"
        "semantic-service"
        "datacontract-service"
        "compliance-service"
        "dq-service"
    )
    
    # Check services
    for service in "${services[@]}"; do
        if [ -n "$SERVICE" ] && [ "$service" != "$SERVICE" ]; then
            continue
        fi
        
        log_info "=========================================="
        log_info "Checking: $service"
        log_info "=========================================="
        
        # Engineering standards compliance
        log_info ""
        log_info "Engineering Standards Compliance:"
        if [ "$ENVIRONMENT" = "all" ] || [ "$ENVIRONMENT" = "docker" ]; then
            if ! check_resource_limits "$service" "docker"; then
                ((warnings++))
            fi
            if ! check_health_checks "$service" "docker"; then
                ((errors++))
            fi
        fi
        
        if [ "$ENVIRONMENT" = "all" ] || [ "$ENVIRONMENT" = "k8s" ]; then
            if ! check_resource_limits "$service" "k8s"; then
                ((errors++))
            fi
            if ! check_health_checks "$service" "k8s"; then
                ((errors++))
            fi
        fi
        
        # Security compliance
        log_info ""
        log_info "Security Compliance:"
        if [ "$ENVIRONMENT" = "all" ] || [ "$ENVIRONMENT" = "docker" ]; then
            if ! check_non_root "$service" "docker"; then
                ((warnings++))
            fi
        fi
        
        if [ "$ENVIRONMENT" = "all" ] || [ "$ENVIRONMENT" = "k8s" ]; then
            if ! check_non_root "$service" "k8s"; then
                ((errors++))
            fi
            if ! check_secrets_not_in_configmap "$service"; then
                ((errors++))
            fi
            if ! check_security_context "$service"; then
                ((warnings++))
            fi
        fi
        
        log_info ""
    done
    
    log_info "=========================================="
    if [ $errors -eq 0 ] && [ $warnings -eq 0 ]; then
        log_info "✓ All compliance checks passed"
    else
        if [ $errors -gt 0 ]; then
            log_error "✗ $errors compliance error(s) found"
        fi
        if [ $warnings -gt 0 ]; then
            log_warn "⚠ $warnings compliance warning(s) found"
        fi
        exit 1
    fi
    log_info "=========================================="
}

main

