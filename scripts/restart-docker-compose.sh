#!/bin/bash
#
# Docker Compose Restart Script
#
# Restarts all services defined in docker-compose.yml by stopping and
# starting them in the correct order.
#
# Usage:
#   ./scripts/restart-docker-compose.sh [--env ENV] [--file FILE] [--skip-build] [--skip-migrations]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --skip-build        Skip building images
#   --skip-migrations   Skip running database migrations
#   --services SERVICES Comma-separated list of services to restart
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
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --skip-migrations)
                SKIP_MIGRATIONS=true
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
Docker Compose Restart Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --skip-build        Skip building images
    --skip-migrations   Skip running database migrations
    --services SERVICES Comma-separated list of services to restart
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --file docker-compose.yml --services api-service,worker-service
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

# Main function
main() {
    log_section "Docker Compose Restart"
    
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Determine compose file
    determine_compose_file
    
    # Stop services
    log_section "Stopping Services"
    local stop_args=()
    if [ -n "$ENVIRONMENT" ]; then
        stop_args+=(--env "$ENVIRONMENT")
    fi
    if [ -n "$COMPOSE_FILE" ]; then
        stop_args+=(--file "$(basename "$COMPOSE_FILE")")
    fi
    if [ -n "$SERVICES" ]; then
        stop_args+=(--services "$SERVICES")
    fi
    
    if ! "$SCRIPT_DIR/stop-docker-compose.sh" "${stop_args[@]}" --timeout 30; then
        log_error "Failed to stop services"
        exit 1
    fi
    
    # Wait a bit for cleanup
    sleep 2
    
    # Start services
    log_section "Starting Services"
    local deploy_args=()
    if [ -n "$ENVIRONMENT" ]; then
        deploy_args+=(--env "$ENVIRONMENT")
    fi
    if [ -n "$COMPOSE_FILE" ]; then
        deploy_args+=(--file "$(basename "$COMPOSE_FILE")")
    fi
    if [ "$SKIP_BUILD" = true ]; then
        deploy_args+=(--skip-build)
    fi
    if [ "$SKIP_MIGRATIONS" = true ]; then
        deploy_args+=(--skip-migrations)
    fi
    if [ -n "$SERVICES" ]; then
        deploy_args+=(--services "$SERVICES")
    fi
    
    if ! "$SCRIPT_DIR/deploy-docker-compose.sh" "${deploy_args[@]}"; then
        log_error "Failed to start services"
        exit 1
    fi
    
    log_section "Restart Complete"
    log_info "Services restarted successfully"
}

# Run main function
main "$@"

