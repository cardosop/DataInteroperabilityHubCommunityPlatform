#!/bin/bash
#
# Docker Compose Cleanup Script
#
# Cleans up Docker Compose resources including containers, volumes, networks,
# and optionally images. Use with caution as this will delete persistent data.
#
# Usage:
#   ./scripts/cleanup-docker-compose.sh [--env ENV] [--file FILE] [--volumes] [--networks] [--images] [--all]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --volumes           Remove volumes (deletes persistent data)
#   --networks          Remove networks
#   --images            Remove images
#   --all               Remove everything (volumes, networks, images)
#   --force             Skip confirmation prompts
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
REMOVE_VOLUMES=false
REMOVE_NETWORKS=false
REMOVE_IMAGES=false
FORCE=false
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
            --volumes)
                REMOVE_VOLUMES=true
                shift
                ;;
            --networks)
                REMOVE_NETWORKS=true
                shift
                ;;
            --images)
                REMOVE_IMAGES=true
                shift
                ;;
            --all)
                REMOVE_VOLUMES=true
                REMOVE_NETWORKS=true
                REMOVE_IMAGES=true
                shift
                ;;
            --force)
                FORCE=true
                shift
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
Docker Compose Cleanup Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --volumes           Remove volumes (deletes persistent data)
    --networks          Remove networks
    --images            Remove images
    --all               Remove everything (volumes, networks, images)
    --force             Skip confirmation prompts
    -h, --help          Show this help message

WARNING: This script will delete data. Use with caution!

Examples:
    $0 --env staging --volumes --networks
    $0 --file docker-compose.yml --all --force
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

# Confirm destructive operations
confirm_action() {
    local message="$1"
    
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    log_warn "$message"
    read -p "Are you sure you want to continue? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        log_info "Operation cancelled"
        return 1
    fi
    
    return 0
}

# Stop and remove containers
stop_and_remove_containers() {
    log_section "Stopping and Removing Containers"
    
    # Stop containers first
    if docker compose -f "$COMPOSE_FILE" stop 2>&1; then
        log_info "Containers stopped"
    else
        log_warn "Some containers may not have been running"
    fi
    
    # Remove containers
    if docker compose -f "$COMPOSE_FILE" rm -f 2>&1; then
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
    
    if ! confirm_action "This will delete all persistent data (databases, object storage, etc.)!"; then
        return 1
    fi
    
    log_section "Removing Volumes"
    
    # Get volume list from compose file
    local volumes
    volumes=$(docker compose -f "$COMPOSE_FILE" config --volumes 2>/dev/null || echo "")
    
    if [ -z "$volumes" ]; then
        log_info "No volumes defined in compose file"
        return 0
    fi
    
    # Remove volumes using docker compose down -v
    if docker compose -f "$COMPOSE_FILE" down -v 2>&1; then
        log_info "Volumes removed"
        
        # Also try to remove volumes directly if they still exist
        for volume in $volumes; do
            if docker volume inspect "$volume" &> /dev/null; then
                if docker volume rm "$volume" 2>&1; then
                    log_info "Removed volume: $volume"
                else
                    log_warn "Could not remove volume: $volume (may be in use)"
                fi
            fi
        done
        
        return 0
    else
        log_error "Failed to remove volumes"
        return 1
    fi
}

# Remove networks
remove_networks() {
    if [ "$REMOVE_NETWORKS" != true ]; then
        return 0
    fi
    
    if ! confirm_action "This will remove Docker networks!"; then
        return 1
    fi
    
    log_section "Removing Networks"
    
    # Get network list from compose file
    local networks
    networks=$(docker compose -f "$COMPOSE_FILE" config --networks 2>/dev/null | grep -E "^  [a-zA-Z0-9_-]+:" | sed 's/://' | sed 's/^  //' || echo "")
    
    if [ -z "$networks" ]; then
        log_info "No networks defined in compose file"
        return 0
    fi
    
    # Remove networks
    for network in $networks; do
        # Get full network name (project_name_network_name)
        local project_name
        project_name=$(basename "$PROJECT_DIR" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]//g')
        local full_network_name="${project_name}_${network}"
        
        if docker network inspect "$full_network_name" &> /dev/null || docker network inspect "$network" &> /dev/null; then
            if docker network rm "$full_network_name" 2>&1 || docker network rm "$network" 2>&1; then
                log_info "Removed network: $network"
            else
                log_warn "Could not remove network: $network (may be in use)"
            fi
        fi
    done
    
    return 0
}

# Remove images
remove_images() {
    if [ "$REMOVE_IMAGES" != true ]; then
        return 0
    fi
    
    if ! confirm_action "This will remove Docker images built for this project!"; then
        return 1
    fi
    
    log_section "Removing Images"
    
    # Get image list from compose file
    local images
    images=$(docker compose -f "$COMPOSE_FILE" config --images 2>/dev/null || echo "")
    
    if [ -z "$images" ]; then
        log_info "No images defined in compose file"
        return 0
    fi
    
    # Remove images
    local removed_count=0
    local failed_count=0
    
    for image in $images; do
        if docker image inspect "$image" &> /dev/null; then
            if docker image rm "$image" 2>&1; then
                log_info "Removed image: $image"
                removed_count=$((removed_count + 1))
            else
                log_warn "Could not remove image: $image (may be in use)"
                failed_count=$((failed_count + 1))
            fi
        fi
    done
    
    log_info "Removed $removed_count image(s), $failed_count failed"
    
    return 0
}

# Clean up orphaned resources
cleanup_orphaned() {
    log_section "Cleaning Up Orphaned Resources"
    
    # Remove stopped containers
    local stopped_containers
    stopped_containers=$(docker ps -a --filter "status=exited" --format "{{.ID}}" | grep -E "hub-|datahub-" || echo "")
    
    if [ -n "$stopped_containers" ]; then
        log_info "Removing stopped containers..."
        echo "$stopped_containers" | xargs -r docker rm -f 2>&1 || true
    fi
    
    # Remove dangling images
    local dangling_images
    dangling_images=$(docker images -f "dangling=true" -q || echo "")
    
    if [ -n "$dangling_images" ]; then
        log_info "Removing dangling images..."
        echo "$dangling_images" | xargs -r docker rmi -f 2>&1 || true
    fi
    
    # Prune system
    log_info "Pruning Docker system..."
    docker system prune -f 2>&1 || true
    
    log_info "Orphaned resources cleaned up"
}

# Main function
main() {
    log_section "Docker Compose Cleanup"
    
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Determine compose file
    determine_compose_file
    
    # Check prerequisites
    check_prerequisites
    
    # Stop and remove containers
    stop_and_remove_containers
    
    # Remove volumes
    remove_volumes
    
    # Remove networks
    remove_networks
    
    # Remove images
    remove_images
    
    # Clean up orphaned resources
    cleanup_orphaned
    
    log_section "Cleanup Complete"
    log_info "Cleanup completed successfully"
    
    if [ "$REMOVE_VOLUMES" = true ]; then
        log_warn "All persistent data has been removed"
        log_info "You will need to run migrations and setup again on next deployment"
    fi
}

# Run main function
main "$@"

