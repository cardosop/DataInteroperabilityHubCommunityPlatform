#!/bin/bash
#
# Docker Performance Optimization Script
#
# Optimizes Docker performance by cleaning up unused resources, pruning system,
# and providing recommendations for Docker daemon configuration.
#
# Usage:
#   ./scripts/optimize-docker-performance.sh [--aggressive] [--dry-run]
#
# Options:
#   --aggressive    Perform aggressive cleanup (removes unused volumes)
#   --dry-run       Show what would be cleaned without actually cleaning
#   --help          Show this help message
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
AGGRESSIVE=false
DRY_RUN=false
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
            --aggressive)
                AGGRESSIVE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
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
Docker Performance Optimization Script

Usage: $0 [OPTIONS]

Options:
    --aggressive    Perform aggressive cleanup (removes unused volumes)
    --dry-run       Show what would be cleaned without actually cleaning
    -h, --help      Show this help message

This script optimizes Docker performance by:
1. Pruning unused containers, networks, and images
2. Removing stopped containers
3. Cleaning up dangling images
4. Optionally removing unused volumes (with --aggressive)
5. Showing Docker disk usage statistics

Examples:
    $0                    # Standard cleanup (safe)
    $0 --aggressive       # Aggressive cleanup (removes volumes)
    $0 --dry-run          # Preview what would be cleaned
EOF
}

# Check prerequisites
check_prerequisites() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
}

# Show Docker disk usage
show_disk_usage() {
    log_section "Docker Disk Usage (Before)"
    docker system df
}

# Prune unused containers
prune_containers() {
    log_section "Pruning Stopped Containers"
    
    if [ "$DRY_RUN" = true ]; then
        local stopped_count
        stopped_count=$(docker ps -a --filter "status=exited" -q | wc -l)
        log_info "Would remove $stopped_count stopped container(s)"
    else
        docker container prune -f
        log_info "Stopped containers pruned"
    fi
}

# Prune unused images
prune_images() {
    log_section "Pruning Unused Images"
    
    if [ "$DRY_RUN" = true ]; then
        local dangling_count
        dangling_count=$(docker images -f "dangling=true" -q | wc -l)
        log_info "Would remove dangling images"
        log_info "Would remove unused images (not currently used by containers)"
    else
        # Remove dangling images first
        docker image prune -f
        # Remove unused images (not currently used by containers)
        docker image prune -af
        log_info "Unused images pruned"
    fi
}

# Prune unused volumes
prune_volumes() {
    if [ "$AGGRESSIVE" != true ]; then
        log_section "Skipping Volume Pruning (use --aggressive to enable)"
        log_warn "Volume pruning skipped. Use --aggressive flag to remove unused volumes."
        return 0
    fi
    
    log_section "Pruning Unused Volumes"
    log_warn "This will remove unused volumes (may delete data)"
    
    if [ "$DRY_RUN" = true ]; then
        local unused_volumes
        unused_volumes=$(docker volume ls -q -f "dangling=true" | wc -l)
        log_info "Would remove $unused_volumes unused volume(s)"
    else
        read -p "Are you sure you want to remove unused volumes? (yes/no): " confirm
        if [ "$confirm" = "yes" ]; then
            docker volume prune -f
            log_info "Unused volumes pruned"
        else
            log_info "Volume pruning cancelled"
        fi
    fi
}

# Prune unused networks
prune_networks() {
    log_section "Pruning Unused Networks"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "Would remove unused networks"
    else
        docker network prune -f
        log_info "Unused networks pruned"
    fi
}

# System-wide prune
system_prune() {
    log_section "System-Wide Prune"
    
    if [ "$DRY_RUN" = true ]; then
        log_info "Would perform system-wide prune"
    else
        docker system prune -af
        log_info "System-wide prune completed"
    fi
}

# Show Docker daemon recommendations
show_recommendations() {
    log_section "Docker Daemon Optimization Recommendations"
    
    cat << EOF
To further optimize Docker performance, consider:

1. **Docker Daemon Configuration** (/etc/docker/daemon.json):
   {
     "max-concurrent-downloads": 10,
     "max-concurrent-uploads": 10,
     "storage-driver": "overlay2",
     "log-driver": "json-file",
     "log-opts": {
       "max-size": "10m",
       "max-file": "3"
     },
     "default-ulimits": {
       "nofile": {
         "Hard": 64000,
         "Name": "nofile",
         "Soft": 64000
       }
     }
   }
   
   Then restart Docker: sudo systemctl restart docker

2. **Monitor Docker Performance**:
   - docker stats --no-stream
   - docker system df
   - docker info | grep -E "Server Version|Storage Driver"

3. **Regular Cleanup**:
   - Run this script regularly: ./scripts/optimize-docker-performance.sh
   - Use --aggressive flag weekly for deep cleanup

4. **Prefect Worker Optimization**:
   - Limit concurrent flow runs (already configured in docker-compose.yml)
   - Monitor Prefect worker logs for Docker timeout errors

EOF
}

# Show final disk usage
show_final_disk_usage() {
    log_section "Docker Disk Usage (After)"
    docker system df
}

# Main function
main() {
    log_section "Docker Performance Optimization"
    
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Check prerequisites
    check_prerequisites
    
    # Show initial disk usage
    show_disk_usage
    
    # Perform cleanup operations
    prune_containers
    prune_images
    prune_volumes
    prune_networks
    
    # System-wide prune (if not dry-run)
    if [ "$DRY_RUN" != true ]; then
        system_prune
    fi
    
    # Show final disk usage
    if [ "$DRY_RUN" != true ]; then
        show_final_disk_usage
    fi
    
    # Show recommendations
    show_recommendations
    
    log_section "Optimization Complete"
    log_info "Docker performance optimization completed successfully"
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "This was a dry run. No changes were made."
        log_info "Run without --dry-run to perform actual cleanup"
    fi
}

# Run main function
main "$@"
