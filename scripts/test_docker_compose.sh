#!/bin/bash
#
# Docker Compose Testing Script
#
# This script validates and tests Docker Compose deployment.
#
# Usage:
#   ./scripts/test_docker_compose.sh [--validate-only] [--file FILE]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

VALIDATE_ONLY=false
COMPOSE_FILE="docker-compose.yml"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --file)
            COMPOSE_FILE="$2"
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

validate_syntax() {
    log_info "Validating Docker Compose syntax: $COMPOSE_FILE"
    
    if docker compose -f "$COMPOSE_FILE" config > /dev/null 2>&1; then
        log_info "✓ Docker Compose syntax is valid"
        return 0
    else
        log_error "✗ Docker Compose syntax validation failed"
        docker compose -f "$COMPOSE_FILE" config
        return 1
    fi
}

check_service_status() {
    local service_name=$1
    
    log_info "Checking status: $service_name"
    
    if docker compose -f "$COMPOSE_FILE" ps "$service_name" | grep -q "Up"; then
        log_info "✓ $service_name is running"
        return 0
    else
        log_error "✗ $service_name is not running"
        return 1
    fi
}

check_service_health() {
    local service_name=$1
    local health_url=$2
    
    log_info "Checking health: $service_name ($health_url)"
    
    # Get container name
    local container_name
    container_name=$(docker compose -f "$COMPOSE_FILE" ps -q "$service_name" | head -1)
    
    if [ -z "$container_name" ]; then
        log_error "✗ Container for $service_name not found"
        return 1
    fi
    
    # Check health using docker inspect
    local health_status
    health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")
    
    if [ "$health_status" = "healthy" ]; then
        log_info "✓ $service_name is healthy"
        return 0
    elif [ "$health_status" = "none" ]; then
        log_warn "⚠ $service_name has no health check configured"
        return 0
    else
        log_error "✗ $service_name health check: $health_status"
        return 1
    fi
}

test_service_communication() {
    local service_name=$1
    local target_service=$2
    local target_port=$3
    
    log_info "Testing communication: $service_name → $target_service:$target_port"
    
    # Get container name
    local container_name
    container_name=$(docker compose -f "$COMPOSE_FILE" ps -q "$service_name" | head -1)
    
    if [ -z "$container_name" ]; then
        log_error "✗ Container for $service_name not found"
        return 1
    fi
    
    # Test connectivity
    if docker exec "$container_name" sh -c "nc -z $target_service $target_port" 2>/dev/null || \
       docker exec "$container_name" sh -c "timeout 2 bash -c '</dev/tcp/$target_service/$target_port'" 2>/dev/null; then
        log_info "✓ $service_name can reach $target_service:$target_port"
        return 0
    else
        log_error "✗ $service_name cannot reach $target_service:$target_port"
        return 1
    fi
}

main() {
    log_info "=========================================="
    log_info "Docker Compose Testing"
    log_info "=========================================="
    log_info ""
    
    local errors=0
    
    # Validate syntax
    if ! validate_syntax; then
        ((errors++))
        exit $errors
    fi
    
    if [ "$VALIDATE_ONLY" = true ]; then
        log_info "Validation only mode - skipping service checks"
        exit 0
    fi
    
    # Check if services are running
    log_info "Checking service status..."
    
    # Define services to check
    declare -a services=(
        "postgres"
        "redis"
        "minio"
        "fuseki"
    )
    
    for service in "${services[@]}"; do
        if ! check_service_status "$service"; then
            ((errors++))
        fi
    done
    
    # Check health
    log_info ""
    log_info "Checking service health..."
    
    declare -A health_endpoints=(
        ["postgres"]="postgres:5432"
        ["redis"]="redis:6379"
        ["minio"]="minio:9000"
        ["fuseki"]="fuseki:3030"
    )
    
    for service in "${!health_endpoints[@]}"; do
        IFS=':' read -r host port <<< "${health_endpoints[$service]}"
        if ! check_service_health "$service" "$host:$port"; then
            ((errors++))
        fi
    done
    
    # Test service communication
    log_info ""
    log_info "Testing service-to-service communication..."
    
    # Test API service → database
    if docker compose -f "$COMPOSE_FILE" ps api-service | grep -q "Up"; then
        if ! test_service_communication "api-service" "postgres" "5432"; then
            ((errors++))
        fi
        if ! test_service_communication "api-service" "redis" "6379"; then
            ((errors++))
        fi
    fi
    
    log_info ""
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All checks passed"
    else
        log_error "✗ $errors check(s) failed"
        exit 1
    fi
    log_info "=========================================="
}

main

