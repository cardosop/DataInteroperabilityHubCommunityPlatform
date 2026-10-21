#!/bin/bash
#
# Service Monitoring Script
#
# Monitors all services in the Docker Compose deployment, including:
# - Service container status
# - Health endpoint status
# - Prometheus metrics (if available)
# - Service performance indicators
#
# Usage:
#   ./scripts/monitor-services.sh [--env ENV] [--file FILE] [--format FORMAT] [--prometheus-url URL] [--services SERVICES]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --format FORMAT     Output format (text, json) - default: text
#   --prometheus-url    Prometheus URL (default: http://localhost:9090)
#   --services SERVICES Comma-separated list of services to monitor
#   --verbose           Verbose output
#   --watch             Watch mode (refresh every 5 seconds)
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${ENVIRONMENT:-}"
COMPOSE_FILE=""
OUTPUT_FORMAT="text"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"
SERVICES=""
VERBOSE=false
WATCH=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Service configuration
declare -A SERVICE_PORTS=(
    ["api-service"]="8000"
    ["worker-service"]="8080"
    ["semantic-service"]="8081"
    ["compliance-service"]="8082"
    ["dq-service"]="8083"
    ["prefect-integration-service"]="8084"
    ["search-service"]="8085"
    ["observability-service"]="8086"
    ["webhook-service"]="8087"
    ["workflow-engine-service"]="8088"
    ["workflow-registry-service"]="8089"
    ["event-bus-health-service"]="8090"
    ["event-schema-registry-service"]="8091"
)

declare -A SERVICE_HEALTH_PATHS=(
    ["api-service"]="/health"
    ["worker-service"]="/healthz"
    ["semantic-service"]="/health"
    ["compliance-service"]="/health"
    ["dq-service"]="/health"
    ["prefect-integration-service"]="/health"
    ["search-service"]="/health"
    ["observability-service"]="/health"
    ["webhook-service"]="/health"
    ["workflow-engine-service"]="/healthz"
    ["workflow-registry-service"]="/health"
    ["event-bus-health-service"]="/healthz"
    ["event-schema-registry-service"]="/health"
)

# Logging functions
log_info() {
    if [ "$VERBOSE" = true ] || [ "$OUTPUT_FORMAT" != "json" ]; then
        echo -e "${GREEN}[INFO]${NC} $1" >&2
    fi
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

log_debug() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${CYAN}[DEBUG]${NC} $1" >&2
    fi
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
            --format)
                OUTPUT_FORMAT="$2"
                shift 2
                ;;
            --prometheus-url)
                PROMETHEUS_URL="$2"
                shift 2
                ;;
            --services)
                SERVICES="$2"
                shift 2
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --watch)
                WATCH=true
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
Service Monitoring Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --format FORMAT     Output format (text, json) - default: text
    --prometheus-url    Prometheus URL (default: http://localhost:9090)
    --services SERVICES Comma-separated list of services to monitor
    --verbose           Verbose output
    --watch             Watch mode (refresh every 5 seconds)
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --file docker-compose.yml --format json
    $0 --services api-service,worker-service --watch
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
    
    log_debug "Using Docker Compose file: $COMPOSE_FILE"
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
    
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        log_error "curl or wget is required for health checks"
        exit 1
    fi
}

# Query Prometheus for metric
query_prometheus() {
    local query="$1"
    local url="${PROMETHEUS_URL}/api/v1/query"
    
    if ! curl -s -f "${url}?query=${query}" 2>/dev/null | grep -q '"status":"success"'; then
        return 1
    fi
    
    curl -s -f "${url}?query=${query}" 2>/dev/null | \
        python3 -c "import sys, json; data=json.load(sys.stdin); print(data['data']['result'][0]['value'][1] if data['data']['result'] else '0')" 2>/dev/null || echo "0"
}

# Check service health endpoint
check_service_health() {
    local service_name="$1"
    local port="${SERVICE_PORTS[$service_name]:-}"
    local health_path="${SERVICE_HEALTH_PATHS[$service_name]:-/health}"
    
    if [ -z "$port" ]; then
        echo "unknown"
        return
    fi
    
    # Try to get container IP or use localhost
    local container_id
    container_id=$(docker compose -f "$COMPOSE_FILE" ps -q "$service_name" 2>/dev/null | head -1)
    
    if [ -z "$container_id" ]; then
        echo "not_running"
        return
    fi
    
    # Try health check via container exec
    if docker exec "$container_id" curl -sf "http://localhost:${port}${health_path}" &> /dev/null || \
       docker exec "$container_id" wget -q --spider "http://localhost:${port}${health_path}" &> /dev/null; then
        echo "healthy"
    else
        echo "unhealthy"
    fi
}

# Get service container status
get_container_status() {
    local service_name="$1"
    local container_id
    container_id=$(docker compose -f "$COMPOSE_FILE" ps -q "$service_name" 2>/dev/null | head -1)
    
    if [ -z "$container_id" ]; then
        echo "not_running"
        return
    fi
    
    docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown"
}

# Get service metrics from Prometheus
get_service_metrics() {
    local service_name="$1"
    local metrics=()
    
    # Try to query Prometheus
    if curl -s -f "${PROMETHEUS_URL}/api/v1/query?query=up" &> /dev/null; then
        # HTTP request rate
        local http_rate
        http_rate=$(query_prometheus "rate(http_requests_total{service=\"${service_name}\"}[5m])" 2>/dev/null || echo "0")
        metrics+=("http_rate:$http_rate")
        
        # Error rate
        local error_rate
        error_rate=$(query_prometheus "rate(http_errors_total{service=\"${service_name}\"}[5m])" 2>/dev/null || echo "0")
        metrics+=("error_rate:$error_rate")
        
        # P95 latency
        local p95_latency
        p95_latency=$(query_prometheus "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service=\"${service_name}\"}[5m]))" 2>/dev/null || echo "0")
        metrics+=("p95_latency:$p95_latency")
    fi
    
    echo "${metrics[*]}"
}

# Monitor all services
monitor_services() {
    local all_services
    all_services=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || echo "")
    
    if [ -z "$all_services" ]; then
        log_error "Could not get service list"
        return 1
    fi
    
    # Filter services if specified
    local services_to_monitor=()
    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        for req_service in "${requested_services[@]}"; do
            for service in $all_services; do
                if [ "$service" = "$req_service" ]; then
                    services_to_monitor+=("$service")
                    break
                fi
            done
        done
    else
        # Monitor all application services (exclude infrastructure)
        local infra_services=("postgres" "redis" "minio" "fuseki" "prometheus" "grafana" "jaeger" "alertmanager" "traefik" "prefect-db" "prefect-server")
        for service in $all_services; do
            local is_infra=false
            for infra in "${infra_services[@]}"; do
                if [ "$service" = "$infra" ]; then
                    is_infra=true
                    break
                fi
            done
            if [ "$is_infra" = false ]; then
                services_to_monitor+=("$service")
            fi
        done
    fi
    
    if [ ${#services_to_monitor[@]} -eq 0 ]; then
        log_warn "No services to monitor"
        return 0
    fi
    
    # Output header
    if [ "$OUTPUT_FORMAT" = "text" ]; then
        echo ""
        echo -e "${BLUE}=== Service Status ===${NC}"
        echo ""
        printf "%-30s %-15s %-15s %-20s\n" "SERVICE" "CONTAINER" "HEALTH" "METRICS"
        echo "--------------------------------------------------------------------------------"
    elif [ "$OUTPUT_FORMAT" = "json" ]; then
        echo "["
    fi
    
    local first=true
    for service in "${services_to_monitor[@]}"; do
        local container_status
        container_status=$(get_container_status "$service")
        local health_status
        health_status=$(check_service_health "$service")
        local metrics
        metrics=$(get_service_metrics "$service")
        
        if [ "$OUTPUT_FORMAT" = "text" ]; then
            local status_color="${GREEN}"
            if [ "$container_status" != "running" ] || [ "$health_status" != "healthy" ]; then
                status_color="${RED}"
            elif [ "$health_status" = "unknown" ]; then
                status_color="${YELLOW}"
            fi
            
            printf "%-30s ${status_color}%-15s${NC} ${status_color}%-15s${NC} %-20s\n" \
                "$service" "$container_status" "$health_status" "$(echo "$metrics" | tr ' ' ',')"
        elif [ "$OUTPUT_FORMAT" = "json" ]; then
            if [ "$first" = false ]; then
                echo ","
            fi
            first=false
            
            cat << EOF
  {
    "service": "$service",
    "container_status": "$container_status",
    "health_status": "$health_status",
    "metrics": "$metrics"
  }
EOF
        fi
    done
    
    if [ "$OUTPUT_FORMAT" = "json" ]; then
        echo "]"
    fi
}

# Main function
main() {
    cd "$PROJECT_DIR"
    
    # Parse arguments
    parse_args "$@"
    
    # Determine compose file
    determine_compose_file
    
    # Check prerequisites
    check_prerequisites
    
    # Monitor services
    if [ "$WATCH" = true ]; then
        while true; do
            clear
            echo -e "${CYAN}Service Monitoring (Press Ctrl+C to exit)${NC}"
            echo ""
            monitor_services
            sleep 5
        done
    else
        monitor_services
    fi
}

# Run main function
main "$@"

