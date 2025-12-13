#!/bin/bash
#
# Workflow Monitoring Script
#
# Monitors workflow execution status, including:
# - Workflow instance counts (running, pending, failed)
# - Workflow execution metrics (duration, success rate)
# - Workflow failure analysis
# - Workflow performance indicators
#
# Usage:
#   ./scripts/monitor-workflows.sh [--env ENV] [--file FILE] [--format FORMAT] [--prometheus-url URL] [--workflow-name NAME]
#
# Options:
#   --env ENV           Environment (dev, staging, production)
#   --file FILE         Specific docker-compose file to use
#   --format FORMAT     Output format (text, json) - default: text
#   --prometheus-url    Prometheus URL (default: http://localhost:9090)
#   --workflow-name     Filter by workflow name
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
WORKFLOW_NAME=""
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
            --workflow-name)
                WORKFLOW_NAME="$2"
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
Workflow Monitoring Script

Usage: $0 [OPTIONS]

Options:
    --env ENV           Environment (dev, staging, production)
    --file FILE         Specific docker-compose file to use
    --format FORMAT     Output format (text, json) - default: text
    --prometheus-url    Prometheus URL (default: http://localhost:9090)
    --workflow-name     Filter by workflow name
    --verbose           Verbose output
    --watch             Watch mode (refresh every 5 seconds)
    -h, --help          Show this help message

Examples:
    $0 --env staging
    $0 --workflow-name contract_creation --format json
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

# Check workflow engine service status
check_workflow_engine_status() {
    local container_id
    container_id=$(docker compose -f "$COMPOSE_FILE" ps -q workflow-engine-service 2>/dev/null | head -1)
    
    if [ -z "$container_id" ]; then
        echo "not_running"
        return
    fi
    
    local status
    status=$(docker inspect --format='{{.State.Status}}' "$container_id" 2>/dev/null || echo "unknown")
    echo "$status"
}

# Get workflow metrics
get_workflow_metrics() {
    local workflow_filter=""
    if [ -n "$WORKFLOW_NAME" ]; then
        workflow_filter="{workflow_name=\"${WORKFLOW_NAME}\"}"
    else
        workflow_filter="{}"
    fi
    
    # Running workflows
    local running
    running=$(query_prometheus "sum(workflow_instances_running${workflow_filter})")
    
    # Pending workflows
    local pending
    pending=$(query_prometheus "sum(workflow_instances_pending${workflow_filter})")
    
    # Failed workflows (current)
    local failed_current
    failed_current=$(query_prometheus "sum(workflow_instances_failed_current${workflow_filter})")
    
    # Total created (rate)
    local created_rate
    created_rate=$(query_prometheus "sum(rate(workflow_instances_created_total${workflow_filter}[5m]))")
    
    # Total completed (rate)
    local completed_rate
    completed_rate=$(query_prometheus "sum(rate(workflow_instances_completed_total${workflow_filter}[5m]))")
    
    # Total failed (rate)
    local failed_rate
    failed_rate=$(query_prometheus "sum(rate(workflow_instances_failed_total${workflow_filter}[5m]))")
    
    # P95 execution duration
    local p95_duration
    p95_duration=$(query_prometheus "histogram_quantile(0.95, sum(rate(workflow_execution_duration_seconds_bucket${workflow_filter}[5m])) by (le))")
    
    # Retry rate
    local retry_rate
    retry_rate=$(query_prometheus "sum(rate(workflow_instances_retried_total${workflow_filter}[5m]))")
    
    # Timeout rate
    local timeout_rate
    timeout_rate=$(query_prometheus "sum(rate(workflow_instances_timed_out_total${workflow_filter}[5m]))")
    
    echo "running:$running pending:$pending failed_current:$failed_current created_rate:$created_rate completed_rate:$completed_rate failed_rate:$failed_rate p95_duration:$p95_duration retry_rate:$retry_rate timeout_rate:$timeout_rate"
}

# Get workflow breakdown by name
get_workflow_breakdown() {
    local query="sum by (workflow_name) (workflow_instances_running{})"
    query_prometheus_labels "$query"
}

# Monitor workflows
monitor_workflows() {
    # Check workflow engine status
    local engine_status
    engine_status=$(check_workflow_engine_status)
    
    if [ "$engine_status" != "running" ]; then
        log_error "Workflow engine service is not running (status: $engine_status)"
        if [ "$OUTPUT_FORMAT" = "json" ]; then
            echo "{\"error\": \"Workflow engine service is not running\", \"status\": \"$engine_status\"}"
        fi
        return 1
    fi
    
    # Get workflow metrics
    local metrics
    metrics=$(get_workflow_metrics)
    
    # Output header
    if [ "$OUTPUT_FORMAT" = "text" ]; then
        echo ""
        echo -e "${BLUE}=== Workflow Status ===${NC}"
        echo ""
        echo -e "Workflow Engine: ${GREEN}$engine_status${NC}"
        echo ""
        echo -e "${CYAN}Overall Metrics:${NC}"
        
        # Parse and display metrics
        for metric in $metrics; do
            local key="${metric%%:*}"
            local value="${metric#*:}"
            printf "  %-25s: %s\n" "$key" "$value"
        done
        
        echo ""
        echo -e "${CYAN}Workflow Breakdown:${NC}"
        
        # Get workflow breakdown
        local breakdown
        breakdown=$(get_workflow_breakdown)
        
        if [ "$breakdown" != "[]" ]; then
            echo "$breakdown" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"{'Workflow Name':<30} {'Running':>10}\")
    print('-' * 42)
    for item in data:
        name = item['labels'].get('workflow_name', 'unknown')
        value = int(item['value'])
        print(f'{name:<30} {value:>10}')
except:
    pass
" 2>/dev/null || echo "  Unable to fetch workflow breakdown"
        else
            echo "  No workflow data available"
        fi
        
    elif [ "$OUTPUT_FORMAT" = "json" ]; then
        local breakdown
        breakdown=$(get_workflow_breakdown)
        
        cat << EOF
{
  "workflow_engine_status": "$engine_status",
  "metrics": {
$(echo "$metrics" | sed 's/\([^:]*\):\([^ ]*\)/    "\1": \2/g' | sed 's/$/,/' | sed '$s/,$//')
  },
  "workflow_breakdown": $breakdown
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
    
    # Monitor workflows
    if [ "$WATCH" = true ]; then
        while true; do
            clear
            echo -e "${CYAN}Workflow Monitoring (Press Ctrl+C to exit)${NC}"
            monitor_workflows
            sleep 5
        done
    else
        monitor_workflows
    fi
}

# Run main function
main "$@"

