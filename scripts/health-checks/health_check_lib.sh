#!/bin/bash
# Health Check Library
# Shared functions for health check scripts

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default compose file
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

# Default timeout for health checks
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-5}"

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*" >&2
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $*"
}

# Detect compose file based on environment
detect_compose_file() {
    local env="${ENVIRONMENT:-}"
    
    if [ -f "docker-compose.staging.yml" ] && [ "${env}" = "staging" ]; then
        COMPOSE_FILE="docker-compose.staging.yml"
    elif [ -f "docker-compose.dev.yml" ] && [ "${env}" = "development" ]; then
        COMPOSE_FILE="docker-compose.dev.yml"
    elif [ -f "docker-compose.yml" ]; then
        COMPOSE_FILE="docker-compose.yml"
    else
        log_error "No docker-compose file found"
        return 1
    fi
    
    log_info "Using compose file: ${COMPOSE_FILE}"
}

# Check if service is running
is_service_running() {
    local service_name="$1"
    
    if docker compose -f "${COMPOSE_FILE}" ps --format json "${service_name}" 2>/dev/null | grep -q '"State":"running"'; then
        return 0
    else
        return 1
    fi
}

# Get service container name
get_container_name() {
    local service_name="$1"
    docker compose -f "${COMPOSE_FILE}" ps --format json "${service_name}" 2>/dev/null | \
        grep -o '"Name":"[^"]*"' | \
        cut -d'"' -f4 | \
        head -1 || echo ""
}

# Get service port mapping
get_service_port() {
    local service_name="$1"
    local internal_port="$2"
    
    # Try to get port from docker compose config
    local port_mapping=$(docker compose -f "${COMPOSE_FILE}" config 2>/dev/null | \
        grep -A 20 "^  ${service_name}:" | \
        grep -E "^\s+-.*:${internal_port}" | \
        head -1 | \
        sed 's/.*"\([0-9]*\):.*/\1/' || echo "")
    
    if [ -n "${port_mapping}" ]; then
        echo "${port_mapping}"
    else
        # Fallback: try to get from running container
        local container_name=$(get_container_name "${service_name}")
        if [ -n "${container_name}" ]; then
            docker port "${container_name}" "${internal_port}/tcp" 2>/dev/null | \
                cut -d':' -f2 || echo ""
        fi
    fi
}

# Check health endpoint via HTTP
check_health_endpoint() {
    local service_name="$1"
    local endpoint="$2"
    local timeout="${3:-${HEALTH_CHECK_TIMEOUT}}"
    
    # Try localhost first
    local url="http://localhost:${endpoint}"
    local response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${timeout}" "${url}" 2>/dev/null || echo "000")
    
    if [ "${response_code}" = "200" ] || [ "${response_code}" = "204" ]; then
        return 0
    fi
    
    # Try container name if localhost fails
    local container_name=$(get_container_name "${service_name}")
    if [ -n "${container_name}" ]; then
        # Extract port from endpoint
        local port=$(echo "${endpoint}" | cut -d'/' -f1 | cut -d':' -f2)
        if [ -z "${port}" ]; then
            port=$(echo "${endpoint}" | cut -d'/' -f1)
        fi
        
        # Try via docker exec
        if docker exec "${container_name}" curl -s -f --max-time "${timeout}" "http://localhost:${endpoint}" >/dev/null 2>&1; then
            return 0
        fi
    fi
    
    return 1
}

# Check service health
check_service_health() {
    local service_name="$1"
    local health_endpoint="$2"
    local description="${3:-${service_name}}"
    
    log_info "Checking ${description}..."
    
    # Check if service is running
    if ! is_service_running "${service_name}"; then
        log_error "${description} is not running"
        return 1
    fi
    
    # Check health endpoint
    if check_health_endpoint "${service_name}" "${health_endpoint}"; then
        log_success "${description} is healthy"
        return 0
    else
        log_error "${description} health check failed (endpoint: ${health_endpoint})"
        return 1
    fi
}

# Check infrastructure service (PostgreSQL, Redis, etc.)
check_infrastructure_service() {
    local service_name="$1"
    local check_command="$2"
    local description="${3:-${service_name}}"
    
    log_info "Checking ${description}..."
    
    # Check if service is running
    if ! is_service_running "${service_name}"; then
        log_error "${description} is not running"
        return 1
    fi
    
    # Execute check command
    local container_name=$(get_container_name "${service_name}")
    if [ -z "${container_name}" ]; then
        log_error "${description} container not found"
        return 1
    fi
    
    if docker exec "${container_name}" ${check_command} >/dev/null 2>&1; then
        log_success "${description} is healthy"
        return 0
    else
        log_error "${description} health check failed"
        return 1
    fi
}

# Print summary
print_summary() {
    local total="$1"
    local passed="$2"
    local failed="$3"
    
    echo ""
    log_info "=========================================="
    log_info "Health Check Summary"
    log_info "=========================================="
    log_info "Total checks: ${total}"
    log_success "Passed: ${passed}"
    if [ "${failed}" -gt 0 ]; then
        log_error "Failed: ${failed}"
    else
        log_info "Failed: ${failed}"
    fi
    log_info "=========================================="
    
    if [ "${failed}" -gt 0 ]; then
        return 1
    else
        return 0
    fi
}

