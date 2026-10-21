#!/bin/bash
#
# Event Bus Monitoring Script
#
# Monitors event bus operations, including:
# - Event publish/consume rates
# - Event processing latency
# - Dead letter queue size
# - Redis connection health
# - Event bus errors and failures
#
# Usage:
#   ./scripts/monitor-event-bus.sh [--env ENV] [--file FILE] [--format FORMAT] [--prometheus-url URL] [--event-type TYPE]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --format FORMAT     Output format (text, json) - default: text
#   --prometheus-url    Prometheus URL (default: http://localhost:9090)
#   --event-type        Filter by event type
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
EVENT_TYPE=""
VERBOSE=false
WATCH=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

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
            --event-type)
                EVENT_TYPE="$2"
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
Event Bus Monitoring Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --format FORMAT     Output format (text, json) - default: text
    --prometheus-url    Prometheus URL (default: http://localhost:9090)
    --event-type        Filter by event type
    --verbose           Verbose output
    --watch             Watch mode (refresh every 5 seconds)
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --event-type contract.created --format json
    $0 --watch
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
    
    if ! command -v curl &> /dev/null; then
        log_error "curl is required for Prometheus queries"
        exit 1
    fi
}

# Query Prometheus for metric
query_prometheus() {
    local query="$1"
    local url="${PROMETHEUS_URL}/api/v1/query"
    
    local result
    result=$(curl -s -f "${url}?query=${query}" 2>/dev/null || echo "")
    
    if [ -z "$result" ]; then
        echo "0"
        return
    fi
    
    # Parse JSON response
    echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('status') == 'success' and data.get('data', {}).get('result'):
        total = sum(float(r['value'][1]) for r in data['data']['result'])
        print(total)
    else:
        print('0')
except:
    print('0')
" 2>/dev/null || echo "0"
}

# Query Prometheus for metric with labels
query_prometheus_labels() {
    local query="$1"
    local url="${PROMETHEUS_URL}/api/v1/query"
    
    local result
    result=$(curl -s -f "${url}?query=${query}" 2>/dev/null || echo "")
    
    if [ -z "$result" ]; then
        echo "[]"
        return
    fi
    
    # Return JSON array of results
    echo "$result" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if data.get('status') == 'success' and data.get('data', {}).get('result'):
        results = []
        for r in data['data']['result']:
            metric = r.get('metric', {})
            value = float(r['value'][1])
            results.append({'labels': metric, 'value': value})
        print(json.dumps(results))
    else:
        print('[]')
except:
    print('[]')
" 2>/dev/null || echo "[]"
}

# Check event bus health service status
check_event_bus_status() {
    local container_id
    container_id=$(docker compose -f "$COMPOSE_FILE" ps -q event-bus-health-service 2>/dev/null | head -1)
    
    if [ -z "$container_id" ]; then
        echo "not_running"
        return
    fi
    
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
    echo "$status"
}

# Get event bus metrics
get_event_bus_metrics() {
    local event_filter=""
    if [ -n "$EVENT_TYPE" ]; then
        event_filter="{event_type=\"${EVENT_TYPE}\"}"
    else
        event_filter="{}"
    fi
    
    # Event publish rate
    local publish_rate
    publish_rate=$(query_prometheus "sum(rate(event_published_total${event_filter}[5m]))")
    
    # Event publish failure rate
    local publish_failure_rate
    publish_failure_rate=$(query_prometheus "sum(rate(event_publish_failed_total${event_filter}[5m]))")
    
    # Event consume rate
    local consume_rate
    consume_rate=$(query_prometheus "sum(rate(event_consumed_total${event_filter}[5m]))")
    
    # Event consume failure rate
    local consume_failure_rate
    consume_failure_rate=$(query_prometheus "sum(rate(event_consume_failed_total${event_filter}[5m]))")
    
    # P95 publish latency
    local p95_publish_latency
    p95_publish_latency=$(query_prometheus "histogram_quantile(0.95, sum(rate(event_publish_duration_seconds_bucket${event_filter}[5m])) by (le))")
    
    # P95 processing latency
    local p95_processing_latency
    p95_processing_latency=$(query_prometheus "histogram_quantile(0.95, sum(rate(event_processing_duration_seconds_bucket${event_filter}[5m])) by (le))")
    
    # DLQ size
    local dlq_size
    dlq_size=$(query_prometheus "sum(event_dlq_size${event_filter})")
    
    # DLQ events rate
    local dlq_events_rate
    dlq_events_rate=$(query_prometheus "sum(rate(event_dlq_events_total${event_filter}[5m]))")
    
    # Redis connection errors
    local redis_connection_errors
    redis_connection_errors=$(query_prometheus "sum(rate(event_bus_redis_connection_errors_total[5m]))")
    
    # Redis pool utilization
    local redis_pool_utilization
    redis_pool_utilization=$(query_prometheus "event_bus_redis_pool_utilization_percent")
    
    # Event bus health status
    local health_status
    health_status=$(query_prometheus "event_bus_health_status")
    
    echo "publish_rate:$publish_rate publish_failure_rate:$publish_failure_rate consume_rate:$consume_rate consume_failure_rate:$consume_failure_rate p95_publish_latency:$p95_publish_latency p95_processing_latency:$p95_processing_latency dlq_size:$dlq_size dlq_events_rate:$dlq_events_rate redis_connection_errors:$redis_connection_errors redis_pool_utilization:$redis_pool_utilization health_status:$health_status"
}

# Get event type breakdown
get_event_type_breakdown() {
    local query="sum by (event_type) (rate(event_published_total{}[5m]))"
    query_prometheus_labels "$query"
}

# Monitor event bus
monitor_event_bus() {
    # Check event bus health service status
    local bus_status
    bus_status=$(check_event_bus_status)
    
    if [ "$bus_status" != "running" ]; then
        log_error "Event bus health service is not running (status: $bus_status)"
        if [ "$OUTPUT_FORMAT" = "json" ]; then
            echo "{\"error\": \"Event bus health service is not running\", \"status\": \"$bus_status\"}"
        fi
        return 1
    fi
    
    # Get event bus metrics
    local metrics
    metrics=$(get_event_bus_metrics)
    
    # Output header
    if [ "$OUTPUT_FORMAT" = "text" ]; then
        echo ""
        echo -e "${BLUE}=== Event Bus Status ===${NC}"
        echo ""
        echo -e "Event Bus Health Service: ${GREEN}$bus_status${NC}"
        echo ""
        echo -e "${CYAN}Overall Metrics:${NC}"
        
        # Parse and display metrics
        for metric in $metrics; do
            local key="${metric%%:*}"
            local value="${metric#*:}"
            local color="${GREEN}"
            
            # Color code based on metric type
            if [[ "$key" == *"failure"* ]] || [[ "$key" == *"error"* ]]; then
                if (( $(echo "$value > 0" | bc -l 2>/dev/null || echo 0) )); then
                    color="${RED}"
                fi
            elif [[ "$key" == "dlq_size" ]]; then
                if (( $(echo "$value > 100" | bc -l 2>/dev/null || echo 0) )); then
                    color="${RED}"
                elif (( $(echo "$value > 10" | bc -l 2>/dev/null || echo 0) )); then
                    color="${YELLOW}"
                fi
            elif [[ "$key" == "health_status" ]]; then
                if (( $(echo "$value != 1" | bc -l 2>/dev/null || echo 0) )); then
                    color="${RED}"
                fi
            fi
            
            printf "  %-30s: ${color}%s${NC}\n" "$key" "$value"
        done
        
        echo ""
        echo -e "${CYAN}Event Type Breakdown:${NC}"
        
        # Get event type breakdown
        local breakdown
        breakdown=$(get_event_type_breakdown)
        
        if [ "$breakdown" != "[]" ]; then
            echo "$breakdown" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"{'Event Type':<40} {'Publish Rate':>15}\")
    print('-' * 57)
    for item in sorted(data, key=lambda x: x['value'], reverse=True):
        event_type = item['labels'].get('event_type', 'unknown')
        value = float(item['value'])
        print(f'{event_type:<40} {value:>15.2f}')
except:
    pass
" 2>/dev/null || echo "  Unable to fetch event type breakdown"
        else
            echo "  No event data available"
        fi
        
    elif [ "$OUTPUT_FORMAT" = "json" ]; then
        local breakdown
        breakdown=$(get_event_type_breakdown)
        
        cat << EOF
{
  "event_bus_status": "$bus_status",
  "metrics": {
$(echo "$metrics" | sed 's/\([^:]*\):\([^ ]*\)/    "\1": \2/g' | sed 's/$/,/' | sed '$s/,$//')
  },
  "event_type_breakdown": $breakdown
}
EOF
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
    
    # Monitor event bus
    if [ "$WATCH" = true ]; then
        while true; do
            clear
            echo -e "${CYAN}Event Bus Monitoring (Press Ctrl+C to exit)${NC}"
            monitor_event_bus
            sleep 5
        done
    else
        monitor_event_bus
    fi
}

# Run main function
main "$@"

