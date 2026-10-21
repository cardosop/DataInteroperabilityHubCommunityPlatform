#!/bin/bash
#
# Docker Compose Stop Script
#
# Gracefully stops all services defined in docker-compose.yml with proper
# shutdown ordering and timeout handling.
#
# Usage:
#   ./scripts/stop-docker-compose.sh [--env ENV] [--file FILE] [--timeout SECONDS] [--remove] [--volumes]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --timeout SECONDS   Stop timeout in seconds (default: 30)
#   --remove            Remove containers after stopping
#   --volumes           Remove volumes after stopping
#   --services SERVICES Comma-separated list of services to stop
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${ENVIRONMENT:-}"
COMPOSE_FILE=""
STOP_TIMEOUT=30
REMOVE_CONTAINERS=false
REMOVE_VOLUMES=false
SERVICES=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --file)
                COMPOSE_FILE="$2"
                shift 2
                ;;
            --timeout)
                STOP_TIMEOUT="$2"
                shift 2
                ;;
            --remove)
                REMOVE_CONTAINERS=true
                shift
                ;;
            --volumes)
                REMOVE_VOLUMES=true
                shift
                ;;
            --services)
                SERVICES="$2"
                shift 2
                ;;
            -h|--help)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    cat << EOF
Docker Compose Stop Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --timeout SECONDS   Stop timeout in seconds (default: 30)
    --remove            Remove containers after stopping
    --volumes           Remove volumes after stopping
    --services SERVICES Comma-separated list of services to stop
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --file docker-compose.yml --timeout 60
    $0 --env production --remove
EOF
}

# Determine compose file based on environment
determine_compose_file() {
    if [ -n "$COMPOSE_FILE" ]; then
        if [ ! -f "$PROJECT_DIR/$COMPOSE_FILE" ]; then
            log_error "Docker Compose file not found: $COMPOSE_FILE"
            exit 1
        fi
        COMPOSE_FILE="$PROJECT_DIR/$COMPOSE_FILE"
        return
    fi
    
    case "$ENVIRONMENT" in
        dev|development)
            COMPOSE_FILE="$PROJECT_DIR/docker-compose.dev.yml"
            ;;
        staging)
            COMPOSE_FILE="$PROJECT_DIR/docker-compose.staging.yml"
            ;;
        production|prod)
            COMPOSE_FILE="$PROJECT_DIR/docker-compose.production.yml"
            ;;
        test)
            COMPOSE_FILE="$PROJECT_DIR/docker-compose.test.yml"
            ;;
        *)
            COMPOSE_FILE="$PROJECT_DIR/docker-compose.yml"
            ;;
    esac
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    log_info "Using Docker Compose file: $COMPOSE_FILE"
}

# Check prerequisites
check_prerequisites() {
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# Stop services in reverse dependency order
stop_services() {
    log_section "Stopping Services"
    
    local compose_args=(-f "$COMPOSE_FILE" stop -t "$STOP_TIMEOUT")
    
    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        compose_args+=("${requested_services[@]}")
    fi
    
    # Stop application services first (they depend on infrastructure)
    local app_services=(
        "traefik"
        "api-service"
        "worker-service"
        "prefect-worker"
        "prefect-server"
        "webhook-service"
        "observability-service"
        "search-service"
        "datacontract-service"
        "compliance-service"
        "dq-service"
        "semantic-service"
        "event-schema-registry-service"
        "event-bus-health-service"
        "workflow-registry-service"
        "workflow-engine-service"
    )
    
    # Stop monitoring services
    local monitoring_services=("alertmanager" "jaeger" "grafana" "prometheus")
    
    # Stop infrastructure services last
    local infra_services=("fuseki" "minio" "redis" "postgres")
    
    # Stop in reverse dependency order
    local all_services=("${app_services[@]}" "${monitoring_services[@]}" "${infra_services[@]}")
    
    if [ -n "$SERVICES" ]; then
        # Filter to requested services only
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for req_service in "${requested_services[@]}"; do
            for service in "${all_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -gt 0 ]; then
            all_services=("${filtered_services[@]}")
        fi
    fi
    
    # Stop services
    for service in "${all_services[@]}"; do
        # Check if service exists in compose file
        if ! docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -q "^${service}$"; then
            continue
        fi
        
        # Check if service is running
        local container_id
        container_id=$(docker compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null | head -1)
        
        if [ -z "$container_id" ]; then
            log_info "Service $service: not running, skipping"
            continue
        fi
        
        log_info "Stopping service: $service"
        if docker compose -f "$COMPOSE_FILE" stop -t "$STOP_TIMEOUT" "$service" 2>&1; then
            log_info "Service $service stopped successfully"
        else
            log_warn "Service $service stop had issues (may already be stopped)"
        fi
    done
    
    # If no specific services requested, stop all remaining services
    if [ -z "$SERVICES" ]; then
        log_info "Stopping all remaining services..."
        if docker compose -f "$COMPOSE_FILE" stop -t "$STOP_TIMEOUT" 2>&1; then
            log_info "All services stopped"
        else
            log_warn "Some services may have already been stopped"
        fi
    fi
}

# Remove containers
remove_containers() {
    if [ "$REMOVE_CONTAINERS" != true ]; then
        return 0
    fi
    
    log_section "Removing Containers"
    
    local compose_args=(-f "$COMPOSE_FILE" rm -f)
    
    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        compose_args+=("${requested_services[@]}")
    fi
    
    if docker compose "${compose_args[@]}" 2>&1; then
        log_info "Containers removed"
        return 0
    else
        log_warn "Some containers may not have been removed"
        return 0
    fi
}

# Remove volumes
remove_volumes() {
    if [ "$REMOVE_VOLUMES" != true ]; then
        return 0
    fi
    
    log_section "Removing Volumes"
    
    log_warn "This will delete all persistent data!"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Volume removal cancelled"
        return 0
    fi
    
    local compose_args=(-f "$COMPOSE_FILE" down -v)
    
    if docker compose "${compose_args[@]}" 2>&1; then
        log_info "Volumes removed"
        return 0
    else
        log_error "Failed to remove volumes"
        return 1
    fi
}

# Verify services are stopped
verify_stopped() {
    log_section "Verifying Services are Stopped"
    
    local running_services=()
    local all_services
    all_services=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || echo "")
    
    if [ -z "$all_services" ]; then
        log_warn "Could not get service list"
        return 0
    fi
    
    for service in $all_services; do
        # Skip if specific services were requested and this isn't one of them
        if [ -n "$SERVICES" ]; then
            local found=false
            local requested_services
            IFS=',' read -ra requested_services <<< "$SERVICES"
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    found=true
                    break
                fi
            done
            if [ "$found" = false ]; then
                continue
            fi
        fi
        
        local container_id
        container_id=$(docker compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null | head -1)
        
        if [ -n "$container_id" ]; then
            local container_status
            container_status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
            
            if [ "$container_status" = "running" ]; then
                running_services+=("$service")
            fi
        fi
    done
    
    if [ ${#running_services[@]} -gt 0 ]; then
        log_warn "Some services are still running: ${running_services[*]}"
        return 1
    fi
    
    log_info "All services are stopped"
    return 0
}

# Main function
main() {
    log_section "Docker Compose Stop"
    
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Determine compose file
    determine_compose_file
    
    # Check prerequisites
    check_prerequisites
    
    # Stop services
    stop_services
    
    # Remove containers if requested
    remove_containers
    
    # Remove volumes if requested
    remove_volumes
    
    # Verify stopped
    verify_stopped
    
    log_section "Stop Complete"
    log_info "Services stopped successfully"
}

# Run main function
main "$@"

