#!/bin/bash
#
# Docker Compose Deployment Script
#
# Deploys all services defined in docker-compose.yml with proper dependency ordering,
# health checks, and error handling.
#
# Usage:
#   ./scripts/deploy-docker-compose.sh [--env ENV] [--file FILE] [--skip-build] [--skip-migrations] [--dry-run]
#
# Options:
#   --env ENV           Environment (dev, staging, production) - determines compose file
#   --file FILE         Specific docker-compose file to use
#   --skip-build        Skip building images
#   --skip-migrations   Skip running database migrations
#   --dry-run           Validate configuration without deploying
#   --force             Force recreate containers
#   --no-deps           Don't start linked services
#   --services SERVICES Comma-separated list of services to deploy
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
SKIP_BUILD=false
SKIP_MIGRATIONS=false
DRY_RUN=false
FORCE_RECREATE=false
NO_DEPS=false
SERVICES=""
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="${PROJECT_DIR}/deployment_logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${LOG_DIR}/deployment_${TIMESTAMP}.log"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Logging functions
log_info() {
    local message="$1"
    echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$LOG_FILE"
}

log_warn() {
    local message="$1"
    echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$LOG_FILE"
}

log_error() {
    local message="$1"
    echo -e "${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE"
}

log_section() {
    local message="$1"
    echo -e "\n${BLUE}=== $message ===${NC}\n" | tee -a "$LOG_FILE"
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
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-migrations)
                SKIP_MIGRATIONS=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE_RECREATE=true
                shift
                ;;
            --no-deps)
                NO_DEPS=true
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
Docker Compose Deployment Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --skip-build        Skip building images
    --skip-migrations   Skip running database migrations
    --dry-run           Validate configuration without deploying
    --force             Force recreate containers
    --no-deps           Don't start linked services
    --services SERVICES Comma-separated list of services to deploy
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --file docker-compose.yml --services postgres,redis
    $0 --env production --skip-build --force
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
        log_info "Available files:"
        ls -1 "$PROJECT_DIR"/docker-compose*.yml 2>/dev/null || true
        exit 1
    fi
    
    log_info "Using Docker Compose file: $COMPOSE_FILE"
}

# Check prerequisites
check_prerequisites() {
    log_section "Checking Prerequisites"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker daemon
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check disk space (at least 10GB free)
    local available_space
    available_space=$(df -BG "$PROJECT_DIR" | tail -1 | awk '{print $4}' | sed 's/G//')
    if [ "$available_space" -lt 10 ]; then
        log_warn "Low disk space: ${available_space}GB available (recommended: 10GB+)"
    fi
    
    log_info "Prerequisites check passed"
}

# Validate Docker Compose configuration
validate_compose_config() {
    log_section "Validating Docker Compose Configuration"
    
    if docker compose -f "$COMPOSE_FILE" config > /dev/null 2>&1; then
        log_info "Docker Compose configuration is valid"
        return 0
    else
        log_error "Docker Compose configuration validation failed"
        docker compose -f "$COMPOSE_FILE" config
        return 1
    fi
}

# Build Docker images
build_images() {
    if [ "$SKIP_BUILD" = true ]; then
        log_info "Skipping image build (--skip-build)"
        return 0
    fi
    
    log_section "Building Docker Images"
    
    local build_args=()
    if [ "$FORCE_RECREATE" = true ]; then
        build_args+=(--no-cache)
    fi
    
    if docker compose -f "$COMPOSE_FILE" build "${build_args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Docker images built successfully"
        return 0
    else
        log_error "Failed to build Docker images"
        return 1
    fi
}

# Start infrastructure services
start_infrastructure() {
    log_section "Starting Infrastructure Services"
    
    local infra_services=("postgres" "redis" "minio" "fuseki")
    local compose_args=(-f "$COMPOSE_FILE" up -d)
    
    if [ "$FORCE_RECREATE" = true ]; then
        compose_args+=(--force-recreate)
    fi
    
    if [ "$NO_DEPS" = true ]; then
        compose_args+=(--no-deps)
    fi
    
    if [ -n "$SERVICES" ]; then
        # Filter infrastructure services from requested services
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${infra_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No infrastructure services to start"
            return 0
        fi
        compose_args+=("${filtered_services[@]}")
    else
        compose_args+=("${infra_services[@]}")
    fi
    
    if docker compose "${compose_args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Infrastructure services started"
    else
        log_error "Failed to start infrastructure services"
        return 1
    fi
    
    # Wait for infrastructure services to be healthy
    wait_for_services_healthy "${infra_services[@]}"
}

# Wait for services to be healthy
wait_for_services_healthy() {
    local services=("$@")
    local max_attempts=120
    local attempt=0
    local all_healthy=false
    
    log_info "Waiting for services to be healthy (max ${max_attempts}s)..."
    
    while [ $attempt -lt $max_attempts ]; do
        all_healthy=true
        
        for service in "${services[@]}"; do
            # Check if service is in the compose file
            if ! docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | grep -q "^${service}$"; then
                continue
            fi
            
            # Check container status
            local container_id
            container_id=$(docker compose -f "$COMPOSE_FILE" ps -q "$service" 2>/dev/null | head -1)
            
            if [ -z "$container_id" ]; then
                all_healthy=false
                break
            fi
            
            # Check health status
            local health_status
            health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_id" 2>/dev/null || echo "none")
            local container_status
            container_status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
            
            if [ "$container_status" != "running" ]; then
                all_healthy=false
                break
            fi
            
            # If health check exists, wait for it to be healthy
            if [ "$health_status" != "none" ] && [ "$health_status" != "healthy" ]; then
                all_healthy=false
                break
            fi
        done
        
        if [ "$all_healthy" = true ]; then
            log_info "All infrastructure services are healthy"
            return 0
        fi
        
        attempt=$((attempt + 1))
        sleep 2
    done
    
    log_error "Timeout waiting for services to be healthy"
    log_info "Service status:"
    docker compose -f "$COMPOSE_FILE" ps
    return 1
}

# Start monitoring services
start_monitoring() {
    log_section "Starting Monitoring Services"
    
    local monitoring_services=("prometheus" "grafana" "jaeger" "alertmanager")
    local compose_args=(-f "$COMPOSE_FILE" up -d)
    
    if [ "$FORCE_RECREATE" = true ]; then
        compose_args+=(--force-recreate)
    fi
    
    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${monitoring_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No monitoring services to start"
            return 0
        fi
        compose_args+=("${filtered_services[@]}")
    else
        compose_args+=("${monitoring_services[@]}")
    fi
    
    if docker compose "${compose_args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Monitoring services started"
        sleep 5  # Give monitoring services time to initialize
        return 0
    else
        log_error "Failed to start monitoring services"
        return 1
    fi
}

# Start application services
start_application_services() {
    log_section "Starting Application Services"
    
    local app_services=(
        "workflow-engine-service"
        "workflow-registry-service"
        "event-bus-health-service"
        "event-schema-registry-service"
        "semantic-service"
        "dq-service"
        "compliance-service"
        "datacontract-service"
        "search-service"
        "observability-service"
        "webhook-service"
        "prefect-server"
        "prefect-worker"
        "api-service"
        "worker-service"
        "traefik"
    )
    
    local compose_args=(-f "$COMPOSE_FILE" up -d)
    
    if [ "$FORCE_RECREATE" = true ]; then
        compose_args+=(--force-recreate)
    fi
    
    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${app_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No application services to start"
            return 0
        fi
        compose_args+=("${filtered_services[@]}")
    else
        compose_args+=("${app_services[@]}")
    fi
    
    if docker compose "${compose_args[@]}" 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Application services started"
        return 0
    else
        log_error "Failed to start application services"
        return 1
    fi
}

# Run database migrations
run_migrations() {
    if [ "$SKIP_MIGRATIONS" = true ]; then
        log_info "Skipping database migrations (--skip-migrations)"
        return 0
    fi
    
    log_section "Running Database Migrations"
    
    # Check if api-service is running
    local api_container
    api_container=$(docker compose -f "$COMPOSE_FILE" ps -q api-service 2>/dev/null | head -1)
    
    if [ -z "$api_container" ]; then
        log_warn "api-service container not found, skipping migrations"
        log_info "Migrations should be run manually after services are started"
        return 0
    fi
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    local max_attempts=60
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-hub}" &> /dev/null; then
            log_info "Database is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Database failed to become ready"
        return 1
    fi
    
    # Run migrations
    log_info "Running Django migrations..."
    if docker compose -f "$COMPOSE_FILE" exec -T api-service python manage.py migrate --noinput 2>&1 | tee -a "$LOG_FILE"; then
        log_info "Database migrations completed successfully"
        return 0
    else
        log_error "Database migrations failed"
        return 1
    fi
}

# Verify deployment
verify_deployment() {
    log_section "Verifying Deployment"
    
    local failed_services=()
    local all_services
    all_services=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || echo "")
    
    if [ -z "$all_services" ]; then
        log_error "Could not get service list"
        return 1
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
        
        if [ -z "$container_id" ]; then
            log_warn "Service $service: container not found"
            failed_services+=("$service")
            continue
        fi
        
        local container_status
        container_status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
        
        if [ "$container_status" != "running" ]; then
            log_error "Service $service: status is $container_status"
            failed_services+=("$service")
            continue
        fi
        
        log_info "Service $service: running"
    done
    
    if [ ${#failed_services[@]} -gt 0 ]; then
        log_error "Deployment verification failed for services: ${failed_services[*]}"
        return 1
    fi
    
    log_info "Deployment verification passed"
    return 0
}

# Main deployment function
main() {
    log_section "Docker Compose Deployment"
    log_info "Log file: $LOG_FILE"
    log_info "Timestamp: $TIMESTAMP"
    
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Determine compose file
    determine_compose_file
    
    # Check prerequisites
    check_prerequisites
    
    # Validate configuration
    if ! validate_compose_config; then
        exit 1
    fi
    
    if [ "$DRY_RUN" = true ]; then
        log_info "Dry run mode - configuration validated successfully"
        exit 0
    fi
    
    # Build images
    if ! build_images; then
        exit 1
    fi
    
    # Start infrastructure
    if ! start_infrastructure; then
        log_error "Failed to start infrastructure services"
        exit 1
    fi
    
    # Start monitoring
    start_monitoring
    
    # Start application services
    if ! start_application_services; then
        log_error "Failed to start application services"
        exit 1
    fi
    
    # Run migrations
    run_migrations
    
    # Verify deployment
    if ! verify_deployment; then
        log_error "Deployment verification failed"
        log_info "Check logs: $LOG_FILE"
        log_info "Check service status: docker compose -f $COMPOSE_FILE ps"
        exit 1
    fi
    
    log_section "Deployment Complete"
    log_info "All services deployed successfully"
    log_info "Log file: $LOG_FILE"
    log_info ""
    log_info "Useful commands:"
    log_info "  View logs: docker compose -f $COMPOSE_FILE logs -f"
    log_info "  Check status: docker compose -f $COMPOSE_FILE ps"
    log_info "  Stop services: ./scripts/stop-docker-compose.sh --file $(basename "$COMPOSE_FILE")"
}

# Run main function
main "$@"

