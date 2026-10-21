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
# Respects explicit COMPOSE_FILE from environment (e.g. COMPOSE_FILE=docker-compose.test.yml)
# Supports ENVIRONMENT=test for E2E test stack (see docs/E2E_ENVIRONMENT_REQUIREMENTS.md)
detect_compose_file() {
    local env="${ENVIRONMENT:-}"

    # Respect explicit COMPOSE_FILE when set to non-default (e.g. docker-compose.test.yml)
    if [ -n "${COMPOSE_FILE}" ] && [ "${COMPOSE_FILE}" != "docker-compose.yml" ]; then
        if [ -f "${COMPOSE_FILE}" ]; then
            log_info "Using compose file: ${COMPOSE_FILE} (from environment)"
            return 0
        fi
        log_error "Compose file not found: ${COMPOSE_FILE}"
        return 1
    fi

    if [ -f "docker-compose.test.yml" ] && [ "${env}" = "test" ]; then
        COMPOSE_FILE="docker-compose.test.yml"
    elif [ -f "docker-compose.staging.yml" ] && [ "${env}" = "staging" ]; then
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

# Get service port mapping (host port for given internal container port)
get_service_port() {
    local service_name="$1"
    local internal_port="$2"
    
    # Try docker compose port first (works when container is running)
    local host_port
    host_port=$(docker compose -f "${COMPOSE_FILE}" port "${service_name}" "${internal_port}" 2>/dev/null | cut -d':' -f2)
    if [ -n "${host_port}" ]; then
        echo "${host_port}"
        return 0
    fi
    
    # Try to get from docker compose config (handles long-form: target: X, published: "Y")
    local config_block
    config_block=$(docker compose -f "${COMPOSE_FILE}" config 2>/dev/null | \
        awk -v svc="${service_name}" '$0 ~ "  " svc ":" {found=1} found {print} found && /^  [a-z]/ && $0 !~ "  " svc ":" {exit}')
    # Match "target: N" (port) then get sibling "published: \"Y\""
    host_port=$(echo "${config_block}" | grep -A 3 "target: ${internal_port}$" | grep "published:" | head -1 | \
        sed -n 's/.*published: *"\([0-9]*\)".*/\1/p')
    if [ -n "${host_port}" ]; then
        echo "${host_port}"
        return 0
    fi
    
    # Fallback: short-form "HOST:CONTAINER" in config
    host_port=$(echo "${config_block}" | grep -oE "\"([0-9]+):${internal_port}\"" | sed 's/.*"\([0-9]*\):.*/\1/' | head -1)
    if [ -n "${host_port}" ]; then
        echo "${host_port}"
        return 0
    fi
    
    # Fallback: docker port from running container
    local container_name
    container_name=$(get_container_name "${service_name}")
    if [ -n "${container_name}" ]; then
        host_port=$(docker port "${container_name}" "${internal_port}/tcp" 2>/dev/null | cut -d':' -f2)
        if [ -n "${host_port}" ]; then
            echo "${host_port}"
        fi
    fi
}

# Check health endpoint via HTTP
check_health_endpoint() {
    local service_name="$1"
    local endpoint="$2"
    local timeout="${3:-${HEALTH_CHECK_TIMEOUT}}"
    
    # Parse endpoint: "PORT/PATH" (e.g. 8000/health or 8000/health/)
    local internal_port path
    internal_port=$(echo "${endpoint}" | cut -d'/' -f1)
    path="/$(echo "${endpoint}" | cut -d'/' -f2-)"
    [[ "$path" == "/" ]] && path=""
    
    # Try localhost first: use host-mapped port when available (e.g. 8001 for api-service-test)
    local host_port
    host_port=$(get_service_port "${service_name}" "${internal_port}")
    if [ -n "${host_port}" ]; then
        local url="http://localhost:${host_port}${path}"
        local response_code
        response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${timeout}" "${url}" 2>/dev/null || echo "000")
        if [ "${response_code}" = "200" ] || [ "${response_code}" = "204" ]; then
            return 0
        fi
    fi
    
    # Fallback: try raw endpoint (for services that bind to same port on host)
    local url="http://localhost:${endpoint}"
    local response_code
    response_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time "${timeout}" "${url}" 2>/dev/null || echo "000")
    if [ "${response_code}" = "200" ] || [ "${response_code}" = "204" ]; then
        return 0
    fi
    
    # Try via docker exec (works when host port is not reachable, e.g. different network)
    local container_name
    container_name=$(get_container_name "${service_name}")
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

